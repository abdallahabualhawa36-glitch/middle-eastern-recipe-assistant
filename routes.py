from flask import render_template, request, jsonify, session, redirect, url_for
from datetime import datetime
from app import app, db
from models import User, Conversation, Message, CookingKnowledgeBase
from utils import generate_audio, extract_recipe_name, get_conversation_history, get_recipe_context
from ai_utils import chain, retrieval_chain, docstore, convstore, instruct_llm, chat_prompt, RExtract, long_reorder, diversify_documents
from werkzeug.security import generate_password_hash, check_password_hash
from langchain_core.runnables import RunnableAssign
from langchain_core.prompts import ChatPromptTemplate  
import os
from langdetect import detect as detect_language
from flask import send_file

cooking_kb_state = {'know_base': CookingKnowledgeBase()}

extract_prompt = ChatPromptTemplate.from_template("""
Extract cooking knowledge from the following conversation:
User: {input}
Assistant: {output}
Current knowledge: {know_base}

Return updated knowledge in JSON format.
{format_instructions}
""")

internal_cooking_chain = RunnableAssign({
    'know_base': RExtract(CookingKnowledgeBase, instruct_llm, extract_prompt)
})


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        if not email or '@' not in email:
            return render_template('register.html', error="Please enter a valid email address.")

        if len(password) < 6:
            return render_template('register.html', error="Password must be at least 6 characters.")

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            return render_template('register.html', error="Email already exists. Please login.")

        new_user = User(
            email=email,
            password_hash=generate_password_hash(password, method='pbkdf2:sha256')
        )

        try:
            db.session.add(new_user)
            db.session.commit()
            session['user'] = new_user.email
            return redirect(url_for('home'))
        except Exception as e:
            db.session.rollback()
            return render_template('register.html', error="An error occurred. Please try again.")

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password_hash, password):
            session['user'] = user.email
            return redirect(url_for('home'))

        return render_template('login.html', error="Invalid email or password")

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

@app.route('/')
def home():
    if 'user' not in session:
        return redirect(url_for('login'))

    user = User.query.filter_by(email=session['user']).first()
    conversations = Conversation.query.filter_by(user_id=user.id).order_by(Conversation.created_at.desc()).all()

    initial_msg = "Hello! I'm your document assistant. Ask me anything about Middle Eastern recipes!"
    return render_template('index.html',
                         initial_message=initial_msg,
                         conversations=conversations,
                         now=datetime.now().strftime("%H:%M"))

@app.route('/chat', methods=['POST'])
def chat():
    if 'user' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        message = data.get('message')
        if not message or not isinstance(message, str):
            return jsonify({'error': 'Message must be a non-empty string'}), 400

        # Detect user language
        user_lang = detect_language(message)

        user = User.query.filter_by(email=session['user']).first()
        conversation_id = data.get('conversation_id')

        if not conversation_id:
            conversation = Conversation(
                user_id=user.id,
                title=message[:50] + ("..." if len(message) > 50 else ""),
                created_at=datetime.utcnow()
            )
            db.session.add(conversation)
            db.session.commit()
            conversation_id = conversation.id
        else:
            conversation = db.session.get(Conversation, conversation_id)
            if not conversation or conversation.user_id != user.id:
                return jsonify({'error': 'Invalid conversation'}), 400

        user_message = Message(
            conversation_id=conversation_id,
            content=message,
            is_user=True,
            timestamp=datetime.utcnow()
        )
        db.session.add(user_message)

        recipe_context = get_recipe_context(conversation_id)
        conversation_history = get_conversation_history(conversation_id, 5)

        # Skyflow integration - Cooking Knowledge Extraction
        state = {
            "input": message,
            "output": "",
            "know_base": cooking_kb_state.get("know_base", CookingKnowledgeBase()).dict()
        }
        
        cooking_kb_state.update(internal_cooking_chain.invoke(state))

        chain_input = {
            "input": message,
            "conversation_id": conversation_id,
            "recipe_context": recipe_context,
            "history": conversation_history,
            "cooking_knowledge": cooking_kb_state["know_base"],
            "user_lang": user_lang  # Add detected language
        }

        docs = docstore.as_retriever(search_kwargs={"k": 20}).invoke(message)
        chain_input["context"] = long_reorder.transform_documents(diversify_documents(docs))

        try:
            response = chain.invoke(chain_input)
        except Exception as e:
            return jsonify({'error': f"Error generating response: {str(e)}"}), 500

        try:
            if ("Recipe:" in response or "الوصفة:" in response) and ("Ingredients" in response or "المكونات" in response):
                recipe_name = extract_recipe_name(response)
                update_recipe_progress(conversation_id, recipe_name, 1)
            elif any(kw in message.lower() for kw in ["next", "continue", "go on", "جاهز", "التالي"]):
                progress = get_recipe_progress(conversation_id)
                if progress and progress.get('has_recipe', False):
                    update_recipe_progress(conversation_id, step_index=progress['step_index'] + 1)
        except Exception as e:
            print(f"Error updating recipe progress: {e}")

        # Generate audio in the detected language
        audio_data = generate_audio(response, lang=user_lang)
        
        bot_message = Message(
            conversation_id=conversation_id,
            content=response,
            is_user=False,
            timestamp=datetime.utcnow()
        )
        db.session.add(bot_message)

        if len(conversation.messages) <= 2:
            conversation.title = message[:50] + ("..." if len(message) > 50 else "")

        convstore.add_texts([f"User: {message}", f"Assistant: {response}"])
        convstore.save_local("convstore_index")

        db.session.commit()

        updated_recipe_context = get_recipe_context(conversation_id) or {
            'current_recipe': None,
            'current_step': 0,
            'has_recipe': False
        }

        return jsonify({
            'response': response,
            'audio': audio_data,
            'conversation_id': conversation_id,
            'current_recipe': updated_recipe_context.get('current_recipe'),
            'current_step': updated_recipe_context.get('current_step', 0),
            'has_recipe': updated_recipe_context.get('has_recipe', False),
            'is_arabic': user_lang == 'ar'  # Add this for frontend RTL support
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/conversations/<int:conversation_id>', methods=['GET'])
def get_conversation(conversation_id):
    if 'user' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    user = User.query.filter_by(email=session['user']).first()
    conversation = Conversation.query.filter_by(id=conversation_id, user_id=user.id).first()

    if not conversation:
        return jsonify({'error': 'Conversation not found'}), 404

    messages = Message.query.filter_by(conversation_id=conversation_id).order_by(Message.timestamp).all()

    recipe_context = get_recipe_context(conversation_id)

    return jsonify({
        'title': conversation.title,
        'messages': [{
            'content': msg.content,
            'is_user': msg.is_user,
            'timestamp': msg.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        } for msg in messages],
        'current_recipe': recipe_context.get('current_recipe'),
        'current_step': recipe_context.get('current_step', 0)
    })

@app.route('/history', methods=['GET'])
def get_history():
    if 'user' not in session:
        return jsonify([])

    user = User.query.filter_by(email=session['user']).first()
    conversations = Conversation.query.filter_by(user_id=user.id).order_by(Conversation.created_at.desc()).all()

    history = [{
        'id': conv.id,
        'title': conv.title,
        'timestamp': conv.created_at.strftime("%Y-%m-%d %H:%M"),
        'preview': conv.messages[0].content[:50] + "..." if conv.messages else ""
    } for conv in conversations]

    return jsonify(history)

@app.route('/clear-history', methods=['POST'])
def clear_history():
    if 'user' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    user = User.query.filter_by(email=session['user']).first()
    Conversation.query.filter_by(user_id=user.id).delete()

    try:
        db.session.commit()
        return jsonify({'status': 'success'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

def update_recipe_progress(conversation_id, recipe_name=None, step_index=None):
    conversation = Conversation.query.get(conversation_id)
    if not conversation:
        return False

    if recipe_name:
        conversation.current_recipe_name = recipe_name
    if step_index is not None:
        conversation.current_step_index = step_index

    try:
        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        print(f"Error updating recipe progress: {e}")
        return False

def get_recipe_progress(conversation_id):
    conversation = Conversation.query.get(conversation_id)
    if not conversation:
        return {
            "recipe_name": None,
            "step_index": 0,
            "has_recipe": False
        }

    return {
        "recipe_name": conversation.current_recipe_name,
        "step_index": conversation.current_step_index,
        "has_recipe": conversation.current_recipe_name is not None
    }
@app.route('/style.css')
def serve_css():
    return send_file('style.css', mimetype='text/css')

@app.route('/script.js')
def serve_js():
    return send_file('script.js', mimetype='application/javascript')
# -*- coding: utf-8 -*-

from flask import request, jsonify
from datetime import datetime, timezone

from app import app, db
from models import Conversation, Message
from utils import get_conversation_history, detect_language
from ai_utils import chain


@app.route('/chat', methods=['POST'])
def chat():

    try:
        data = request.get_json()

        if not data:
            return jsonify({
                'error': 'No data provided'
            }), 400


        message = data.get('message')
        user_id = data.get('user_id')
        conversation_id = data.get('conversation_id')

        if not message or not isinstance(message, str):
            return jsonify({
                'error': 'Message must be a non-empty string'
            }), 400

        if not user_id:
            return jsonify({
                'error': 'user_id is required'
            }), 400

        user_lang = detect_language(message)


        if not conversation_id:

            conversation = Conversation(
                user_id=user_id,
                title=(
                    message[:50]
                    + ("..." if len(message) > 50 else "")
                ),
                created_at=datetime.now(timezone.utc)
            )

            db.session.add(conversation)
            db.session.commit()

            conversation_id = conversation.id

        else:

            conversation = db.session.get(
                Conversation,
                conversation_id
            )

            if not conversation:
                return jsonify({
                    'error': 'Invalid conversation'
                }), 400

            # Make sure conversation belongs to this user
            if conversation.user_id != user_id:
                return jsonify({
                    'error': 'Invalid conversation'
                }), 403


        user_message = Message(
            conversation_id=conversation_id,
            content=message,
            is_user=True,
            timestamp=datetime.now(timezone.utc)
        )

        db.session.add(user_message)
        db.session.commit()


        conversation_history = get_conversation_history(
            conversation_id,
            5
        )


        product_context = data.get(
            'product_context',
            []
        )

        shopping_state = data.get(
            'shopping_state',
            {}
        )

        chain_input = {
            "input": message,

            "history": conversation_history,

            "product_context": product_context,

            "shopping_state": shopping_state,

            "user_lang": user_lang
        }


        print("\n==============================================")
        print("🛒 SHOPPING AI REQUEST")
        print("==============================================")
        print("👤 USER ID:", user_id)
        print("💬 MESSAGE:", message)
        print("🌐 LANGUAGE:", user_lang)
        print("💬 CONVERSATION ID:", conversation_id)
        print("==============================================")


        try:

            response = chain.invoke(
                chain_input
            )

        except Exception as e:

            print(
                f"❌ AI Error: "
                f"{type(e).__name__}: {e}"
            )

            db.session.rollback()

            return jsonify({
                'error': (
                    f'Error generating response: {str(e)}'
                )
            }), 500


        bot_message = Message(
            conversation_id=conversation_id,
            content=response,
            is_user=False,
            timestamp=datetime.now(timezone.utc)
        )

        db.session.add(bot_message)


        if len(conversation.messages) <= 2:

            conversation.title = (
                message[:50]
                + ("..." if len(message) > 50 else "")
            )


        db.session.commit()


        print("✅ AI RESPONSE SAVED")
        print("==============================================\n")


        return jsonify({

            'response': response,

            'conversation_id': conversation_id,

            'is_arabic': user_lang == 'ar',

            'timestamp': datetime.now(
                timezone.utc
            ).isoformat()
        })


    except Exception as e:

        db.session.rollback()

        print(
            f"❌ Chat Error: "
            f"{type(e).__name__}: {e}"
        )

        return jsonify({
            'error': str(e)
        }), 500


@app.route(
    '/conversations/<int:conversation_id>',
    methods=['GET']
)
def get_conversation(conversation_id):

    user_id = request.args.get(
        'user_id',
        type=int
    )

    if not user_id:

        return jsonify({
            'error': 'user_id is required'
        }), 400


    conversation = (
        Conversation.query
        .filter_by(
            id=conversation_id,
            user_id=user_id
        )
        .first()
    )


    if not conversation:

        return jsonify({
            'error': 'Conversation not found'
        }), 404


    messages = (
        Message.query
        .filter_by(
            conversation_id=conversation_id
        )
        .order_by(
            Message.timestamp
        )
        .all()
    )


    return jsonify({

        'title': conversation.title,

        'messages': [

            {
                'content': msg.content,

                'is_user': msg.is_user,

                'timestamp': msg.timestamp.strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            }

            for msg in messages
        ]
    })


@app.route('/history', methods=['GET'])
def get_history():

    user_id = request.args.get(
        'user_id',
        type=int
    )

    if not user_id:

        return jsonify({
            'error': 'user_id is required'
        }), 400


    conversations = (
        Conversation.query
        .filter_by(
            user_id=user_id
        )
        .order_by(
            Conversation.created_at.desc()
        )
        .all()
    )


    history = [

        {
            'id': conv.id,

            'title': conv.title,

            'timestamp': conv.created_at.strftime(
                "%Y-%m-%d %H:%M"
            ),

            'preview': (
                conv.messages[0].content[:50] + "..."
                if conv.messages
                else ""
            )
        }

        for conv in conversations
    ]


    return jsonify(history)


@app.route(
    '/clear-history',
    methods=['POST']
)
def clear_history():

    data = request.get_json() or {}

    user_id = data.get('user_id')


    if not user_id:

        return jsonify({
            'error': 'user_id is required'
        }), 400


    try:

        Conversation.query.filter_by(
            user_id=user_id
        ).delete(
            synchronize_session=False
        )

        db.session.commit()


        return jsonify({
            'status': 'success'
        })


    except Exception as e:

        db.session.rollback()

        return jsonify({
            'error': str(e)
        }), 500
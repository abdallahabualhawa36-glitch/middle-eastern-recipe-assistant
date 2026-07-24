import os
import io
import base64
import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from gtts import gTTS
import fitz  # PyMuPDF
from langchain_core.documents import Document


def generate_audio(text, lang='en'):
    try:
        if lang == 'auto':
            lang = 'ar' if detect_language(text) == 'ar' else 'en'

        def synthesize_audio():
            tts = gTTS(text, lang=lang)
            buffer = io.BytesIO()
            tts.write_to_fp(buffer)
            return base64.b64encode(buffer.getvalue()).decode('utf-8')

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(synthesize_audio)
            return future.result(timeout=8)
    except (FuturesTimeoutError, TimeoutError, Exception) as e:
        print("Audio error:", e)
        return None

def extract_recipe_name(response_text):
    # English patterns
    en_patterns = [
        r"Recipe:\s*(.*?)\n",
        r"Recipe\s*name:\s*(.*?)\n",
        r"^(.*?)\nIngredients:",
        r"Let's make (.*?)\.",
        r"How to make (.*?)\n"
    ]
    
    # Arabic patterns
    ar_patterns = [
        r"الوصفة:\s*(.*?)\n",
        r"اسم الوصفة:\s*(.*?)\n",
        r"^(.*?)\nالمكونات:",
        r"لنحضر (.*?)\.",
        r"طريقة عمل (.*?)\n"
    ]
    
    # Try Arabic patterns first
    for pattern in ar_patterns:
        match = re.search(pattern, response_text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    
    # Then try English patterns
    for pattern in en_patterns:
        match = re.search(pattern, response_text, re.IGNORECASE)
        if match:
            return match.group(1).strip()

    first_line = response_text.split('\n')[0].strip()
    if "Ingredients" not in first_line and "Step" not in first_line and "المكونات" not in first_line and "الخطوة" not in first_line:
        return first_line
    
    # Detect language for unknown recipe
    if detect_language(response_text) == 'ar':
        return "وصفة غير معروفة"
    return "Unknown Recipe"

def get_conversation_history(conversation_id, limit=5):
    from models import Message
    messages = Message.query.filter_by(conversation_id=conversation_id).order_by(Message.timestamp.desc()).limit(limit).all()
    return "\n".join(
        f"{'User' if msg.is_user else 'Assistant'}: {msg.content}"
        for msg in reversed(messages)
    )

def get_recipe_context(conversation_id):
    from models import Conversation, Message
    conversation = Conversation.query.get(conversation_id)
    if not conversation:
        return {
            'current_recipe': None,
            'current_step': 0,
            'has_recipe': False
        }


    messages = Message.query.filter_by(conversation_id=conversation_id).order_by(Message.timestamp.desc()).limit(3).all()

    current_recipe = conversation.current_recipe_name
    if current_recipe:
        for msg in messages:
            if current_recipe.lower() not in msg.content.lower() and not msg.is_user:
                current_recipe = None
                break

    return {
        'current_recipe': current_recipe or conversation.current_recipe_name,
        'current_step': conversation.current_step_index,
        'has_recipe': conversation.current_recipe_name is not None
    }
def load_local_pdfs(pdf_paths):
    """Load and extract text from local PDF files using PyMuPDF"""
    from langchain_core.documents import Document  # ✅ بدلاً من langchain.docstore.document

def load_local_pdfs(pdf_paths):
    """Load and extract text from local PDF files using PyMuPDF"""
    documents = []
    
    for pdf_path in pdf_paths:
        try:
            # Check if file exists
            if not os.path.exists(pdf_path):
                print(f"File not found: {pdf_path}")
                continue
                
            doc = fitz.open(pdf_path)
            text = ""
            for page in doc:
                text += page.get_text()
                
            documents.append(Document(
                page_content=text,
                metadata={"source": pdf_path, "Title": os.path.basename(pdf_path)}
            ))
        except Exception as e:
            print(f"Error loading {pdf_path}: {e}")
    
    return documents
def detect_language(text):
    """
    Detect if the text is primarily in Arabic or English
    """
    arabic_chars = sum(1 for char in text if '\u0600' <= char <= '\u06FF')
    return 'ar' if arabic_chars / max(len(text), 1) > 0.3 else 'en'
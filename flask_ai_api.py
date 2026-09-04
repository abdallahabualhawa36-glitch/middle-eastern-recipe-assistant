# -*- coding: utf-8 -*-

from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy

import json
import re
from datetime import datetime, timezone

from ai_utils import chain, instruct_llm
from utils import detect_language, get_conversation_history


app = Flask(__name__)
CORS(app)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///ai_conversations.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'connect_args': {
        'timeout': 30
    }
}

db = SQLAlchemy(app)


class Conversation(db.Model):
    id = db.Column(
        db.Integer,
        primary_key=True
    )

    user_id = db.Column(
        db.Integer,
        nullable=False
    )

    title = db.Column(
        db.String(200),
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc)
    )

    current_product = db.Column(
        db.String(200),
        nullable=True
    )

    messages = db.relationship(
        'Message',
        backref='conversation',
        lazy=True,
        cascade='all, delete-orphan'
    )


class Message(db.Model):
    id = db.Column(
        db.Integer,
        primary_key=True
    )

    conversation_id = db.Column(
        db.Integer,
        db.ForeignKey('conversation.id'),
        nullable=False
    )

    content = db.Column(
        db.Text,
        nullable=False
    )

    is_user = db.Column(
        db.Boolean,
        nullable=False
    )

    timestamp = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc)
    )


with app.app_context():
    db.create_all()


def extract_products_from_response(response):
    products = []

    patterns = [
        r'(?:recommend|أنصحك بـ)\s*["\']?([^"\']+?)["\']?',
        r'(?:product|المنتج)\s*:?\s*([^\n,]+)',
        r'(?:Model|الموديل)\s*:?\s*([^\n,]+)'
    ]

    for pattern in patterns:
        matches = re.findall(
            pattern,
            response,
            re.IGNORECASE
        )

        products.extend(
            match.strip()
            for match in matches
            if match.strip()
        )

    seen = set()
    unique = []

    for product in products:
        product_lower = product.lower()

        if product_lower not in seen:
            seen.add(product_lower)
            unique.append(product)

    return unique[:10]


def filter_products_for_query(
    products,
    message,
    max_results=15
):
    if not products:
        return []

    query = message.lower().strip()

    category_keywords = {
        "iphone": [
            "iphone",
            "آيفون",
            "ايفون",
            "آبل فون",
            "هاتف",
            "تلفون",
            "موبايل",
            "جوال",
            "phone",
            "smartphone"
        ],
        "mac": [
            "mac",
            "ماك",
            "macbook",
            "ماك بوك",
            "imac",
            "آي ماك",
            "اي ماك",
            "mac mini",
            "mac studio"
        ],
        "ipad": [
            "ipad",
            "آيباد",
            "ايباد"
        ],
        "watch": [
            "apple watch",
            "watch",
            "ساعة",
            "ابل واتش",
            "آبل واتش"
        ],
        "airpods": [
            "airpods",
            "air pods",
            "ايربودز",
            "إيربودز"
        ],
        "accessory": [
            "charger",
            "شاحن",
            "adapter",
            "ادابتر",
            "محول",
            "cable",
            "كيبل",
            "كابل",
            "case",
            "كفر",
            "غطاء",
            "keyboard",
            "كيبورد",
            "mouse",
            "ماوس"
        ]
    }

    detected_category = None

    for category, keywords in category_keywords.items():
        if any(keyword in query for keyword in keywords):
            detected_category = category
            break

    max_price = None
    min_price = None

    max_price_patterns = [
        r"(?:تحت|أقل من|اقل من|بحد أقصى|حد أقصى|ميزانية|budget)\s*(?:من)?\s*(\d+(?:\.\d+)?)",
        r"(?:under|below|less than|max|maximum|budget)\s*\$?\s*(\d+(?:\.\d+)?)"
    ]

    min_price_patterns = [
        r"(?:فوق|أكثر من|اكثر من|أعلى من|اعلى من)\s*(\d+(?:\.\d+)?)",
        r"(?:above|over|more than|greater than|minimum)\s*\$?\s*(\d+(?:\.\d+)?)"
    ]

    for pattern in max_price_patterns:
        match = re.search(pattern, query)
        if match:
            max_price = float(match.group(1))
            break

    for pattern in min_price_patterns:
        match = re.search(pattern, query)
        if match:
            min_price = float(match.group(1))
            break

    filtered = []

    for product in products:
        name = str(product.get("name", "")).lower()
        brand = str(product.get("brand", "")).lower()
        description = str(product.get("description", "")).lower()
        tags = str(product.get("tags", "")).lower()

        searchable_text = " ".join([
            name,
            brand,
            description,
            tags
        ])

        if detected_category == "iphone":
            category_match = (
                "iphone" in searchable_text
                or "آيفون" in searchable_text
                or "ايفون" in searchable_text
            )

        elif detected_category == "mac":
            category_match = (
                "mac" in searchable_text
                or "macbook" in searchable_text
                or "imac" in searchable_text
                or "ماك" in searchable_text
            )

        elif detected_category == "ipad":
            category_match = (
                "ipad" in searchable_text
                or "آيباد" in searchable_text
                or "ايباد" in searchable_text
            )

        elif detected_category == "watch":
            category_match = (
                "watch" in searchable_text
                or "ساعة" in searchable_text
                or "واتش" in searchable_text
            )

        elif detected_category == "airpods":
            category_match = (
                "airpods" in searchable_text
                or "air pods" in searchable_text
                or "ايربودز" in searchable_text
                or "إيربودز" in searchable_text
            )

        elif detected_category == "accessory":
            accessory_words = category_keywords["accessory"]
            category_match = any(
                word in searchable_text
                for word in accessory_words
            )

        else:
            category_match = True

        if not category_match:
            continue

        price = product.get("price")

        try:
            price = float(price)
        except (TypeError, ValueError):
            price = None

        if max_price is not None:
            if price is None or price > max_price:
                continue

        if min_price is not None:
            if price is None or price < min_price:
                continue

        filtered.append(product)

        if len(filtered) >= max_results:
            break

    if detected_category is None and max_price is None and min_price is None:
        return products[:max_results]

    return filtered


@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'healthy',
        'service': 'AI Shopping Assistant',
        'version': '1.0.0'
    })


@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.get_json(silent=True) or {}

    message = data.get('message', '')
    user_id = data.get('user_id')
    conversation_id = data.get('conversation_id')

    product_context = data.get(
        'product_context',
        []
    )
    print("\n📦 PRODUCTS RECEIVED FROM LARAVEL:", len(product_context))

    if product_context:
     print("🛍️ FIRST PRODUCTS:", [p.get("name") for p in product_context[:5]])

    shopping_state = data.get(
        'shopping_state',
        {}
    )

    if not message:
        return jsonify({
            'error': 'Message required'
        }), 400

    if not user_id:
        return jsonify({
            'error': 'user_id required'
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
        conversation = Conversation.query.get(
            conversation_id
        )

        if not conversation:
            return jsonify({
                'error': 'Conversation not found'
            }), 404

        if conversation.user_id != user_id:
            return jsonify({
                'error': 'Unauthorized conversation access'
            }), 403

    user_msg = Message(
        conversation_id=conversation_id,
        content=message,
        is_user=True,
        timestamp=datetime.now(timezone.utc)
    )

    db.session.add(user_msg)
    db.session.commit()

    history = get_conversation_history(
        conversation_id,
        Message,
        5
    )

    filtered_products = filter_products_for_query(
        product_context,
        message,
        max_results=15
    )

    print("\n🔎 USER QUERY:", message)
    print(
        "📦 ALL PRODUCTS:",
        len(product_context)
    )
    print(
        "🎯 PRODUCTS SENT TO AI:",
        len(filtered_products)
    )

    if filtered_products:
        print(
            "🛍️ MATCHED PRODUCTS:",
            [
                product.get("name")
                for product in filtered_products
            ]
        )

    chain_input = {
        "input": message,
        "history": history,
        "product_context": json.dumps(
            filtered_products,
            ensure_ascii=False
        ),
        "shopping_state": json.dumps(
            shopping_state,
            ensure_ascii=False
        ),
        "user_lang": user_lang
    }

    print("🔥 STARTING AI...")

    try:
        response = chain.invoke(
            chain_input
        )

        print("🔥 AI FINISHED!")

    except Exception as e:
        print(
            f"🔥 DETAILED ERROR: "
            f"{type(e).__name__}: {e}"
        )

        return jsonify({
            'error': f"AI Error: {str(e)}"
        }), 500

    bot_msg = Message(
        conversation_id=conversation_id,
        content=response,
        is_user=False,
        timestamp=datetime.now(timezone.utc)
    )

    db.session.add(bot_msg)
    db.session.commit()

    mentioned_products = extract_products_from_response(
        response
    )

    return jsonify({
        'response': response,
        'conversation_id': conversation_id,
        'is_arabic': user_lang == 'ar',
        'mentioned_products': mentioned_products,
        'timestamp': datetime.now(
            timezone.utc
        ).isoformat()
    })


@app.route('/api/search', methods=['POST'])
def search_products():
    data = request.get_json(silent=True) or {}

    query = data.get('query', '')
    preferences = data.get(
        'preferences',
        {}
    )

    if not query:
        return jsonify({
            'error': 'Query required'
        }), 400

    analysis_prompt = f"""
Analyze the following user query and extract
product search criteria.

Query: "{query}"

Return ONLY a JSON object with these fields:

- category: string
  (iphone, mac, ipad, watch, airpods, accessory, general)

- brand: string (if mentioned)

- max_price: number (if mentioned)

- min_price: number (if mentioned)

- features: array of strings

- intent: string
  (purchase, comparison, information)
"""

    try:
        analysis = instruct_llm.invoke(
            analysis_prompt
        )

        json_match = re.search(
            r'\{.*\}',
            analysis.content,
            re.DOTALL
        )

        if json_match:
            criteria = json.loads(
                json_match.group()
            )
        else:
            criteria = {
                'category': 'general',
                'intent': 'search'
            }

    except Exception:
        criteria = {
            'category': 'general',
            'intent': 'search'
        }

    return jsonify({
        'query': query,
        'interpreted_criteria': criteria,
        'preferences': preferences
    })


@app.route('/api/recommend', methods=['POST'])
def recommend_products():
    data = request.get_json(silent=True) or {}

    conversation_id = data.get(
        'conversation_id'
    )

    limit = data.get(
        'limit',
        5
    )

    if not conversation_id:
        return jsonify({
            'error': 'conversation_id required'
        }), 400

    messages = (
        Message.query
        .filter_by(
            conversation_id=conversation_id
        )
        .order_by(
            Message.timestamp.desc()
        )
        .limit(10)
        .all()
    )

    if not messages:
        return jsonify({
            'recommendations': []
        })

    conversation_text = "\n".join(
        [
            (
                f"{'User' if m.is_user else 'Assistant'}: "
                f"{m.content}"
            )
            for m in reversed(messages)
        ]
    )

    recommendation_prompt = f"""
Based on this conversation, recommend products
the user might be interested in.

Conversation:

{conversation_text}

Return a JSON array of product types with:

- product_type: string
- reason: string
- key_features: array of strings
"""

    try:
        recommendation = instruct_llm.invoke(
            recommendation_prompt
        )

        json_match = re.search(
            r'\[.*\]',
            recommendation.content,
            re.DOTALL
        )

        if json_match:
            recommendations = json.loads(
                json_match.group()
            )
        else:
            recommendations = []

    except Exception:
        recommendations = []

    return jsonify({
        'recommendations': recommendations[:limit],
        'count': len(
            recommendations[:limit]
        )
    })


if __name__ == '__main__':
    app.run(
        host='0.0.0.0',
        port=5001,
        debug=False
    )
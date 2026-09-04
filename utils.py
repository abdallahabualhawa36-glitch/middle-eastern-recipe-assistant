def get_conversation_history(conversation_id, limit=5):
    from models import Message

    messages = (
        Message.query
        .filter_by(conversation_id=conversation_id)
        .order_by(Message.timestamp.desc())
        .limit(limit)
        .all()
    )

    return "\n".join(
        f"{'User' if msg.is_user else 'Assistant'}: {msg.content}"
        for msg in reversed(messages)
    )


def detect_language(text):
    arabic_chars = sum(
        1
        for char in text
        if '\u0600' <= char <= '\u06FF'
    )

    return 'ar' if arabic_chars / max(len(text), 1) > 0.3 else 'en'
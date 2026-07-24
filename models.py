from datetime import datetime
from app import db
from pydantic import BaseModel, Field

class CookingKnowledgeBase(BaseModel):
    current_recipe: str = Field('unknown', description="The recipe the user is currently making")
    current_step: int = Field(0, description="The current step the user is on")
    user_preference: str = Field('', description="User's dietary or flavor preferences")
    unresolved_questions: str = Field('', description="Any open questions the assistant should clarify")
    goal: str = Field('', description="The user's current cooking goal or request")

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(150), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    conversations = db.relationship('Conversation', backref='user', lazy=True, cascade='all, delete-orphan')

class Conversation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    current_recipe_name = db.Column(db.String(200), nullable=True)
    current_step_index = db.Column(db.Integer, default=0)
    messages = db.relationship('Message', backref='conversation', lazy=True, cascade='all, delete-orphan')

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey('conversation.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_user = db.Column(db.Boolean, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
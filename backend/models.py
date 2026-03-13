from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from datetime import datetime

Base = declarative_base()

class ChatHistory(Base):
    """Chat history model for storing conversation messages."""
    __tablename__ = "chat_history"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(String(255), nullable=False, index=True)
    conversation_id = Column(String(255), nullable=False, index=True)
    message_type = Column(String(50), nullable=False)  # 'AI' or 'Human'
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    is_deleted = Column(Boolean, default=False, nullable=False)
    
    # Create composite index for efficient queries
    __table_args__ = (
        Index('ix_chat_history_user_conversation', 'user_id', 'conversation_id'),
        Index('ix_chat_history_timestamp', 'timestamp'),
    )
    
    def to_dict(self):
        """Convert model instance to dictionary."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'conversation_id': self.conversation_id,
            'message_type': self.message_type,
            'content': self.content,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'is_deleted': self.is_deleted
        }

class User(Base):
    """User model for storing user information."""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True, unique=True)
    password_hash = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_active = Column(DateTime(timezone=True), server_default=func.now())
    is_active = Column(Boolean, default=True)
    
    def to_dict(self):
        """Convert model instance to dictionary."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'username': self.username,
            'email': self.email,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_active': self.last_active.isoformat() if self.last_active else None,
            'is_active': self.is_active
        }

class Conversation(Base):
    """Conversation model for tracking chat sessions."""
    __tablename__ = "conversations"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    conversation_id = Column(String(255), unique=True, nullable=False, index=True)
    user_id = Column(String(255), nullable=False, index=True)
    title = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    is_active = Column(Boolean, default=True)
    message_count = Column(Integer, default=0)
    
    def to_dict(self):
        """Convert model instance to dictionary."""
        return {
            'id': self.id,
            'conversation_id': self.conversation_id,
            'user_id': self.user_id,
            'title': self.title,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'is_active': self.is_active,
            'message_count': self.message_count
        }
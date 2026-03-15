from sqlalchemy.orm import Session
from sqlalchemy import desc, and_, func
from typing import List, Optional, Tuple
from datetime import datetime
import uuid
import google.generativeai as genai

from models import ChatHistory, User, Conversation
from schemas import (
    ChatMessageCreate, ChatRequest, ConversationCreate, UserCreate,
    MessageType, ConversationUpdateRequest, UserRegister
)
from auth import verify_password, get_password_hash

class ChatService:
    """Service for handling chat operations."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def add_message(self, message_data: ChatMessageCreate) -> ChatHistory:
        """Add a message to chat history."""
        db_message = ChatHistory(
            user_id=message_data.user_id,
            conversation_id=message_data.conversation_id,
            message_type=message_data.message_type.value,
            content=message_data.content
        )
        self.db.add(db_message)
        self.db.commit()
        self.db.refresh(db_message)
        
        # Update conversation message count
        self._update_conversation_message_count(message_data.conversation_id)
        
        return db_message
    
    def get_conversation_history(self, user_id: str, conversation_id: str) -> List[ChatHistory]:
        """Get all messages for a conversation."""
        return self.db.query(ChatHistory).filter(
            and_(
                ChatHistory.user_id == user_id,
                ChatHistory.conversation_id == conversation_id,
                ChatHistory.is_deleted == False
            )
        ).order_by(ChatHistory.timestamp.asc()).all()
    
    def get_recent_messages(self, user_id: str, conversation_id: str, limit: int = 50) -> List[ChatHistory]:
        """Get recent messages for context (returned in chronological order)."""
        # Subquery to get the most recent N messages, then re-sort ascending
        subquery = self.db.query(ChatHistory).filter(
            and_(
                ChatHistory.user_id == user_id,
                ChatHistory.conversation_id == conversation_id,
                ChatHistory.is_deleted == False
            )
        ).order_by(desc(ChatHistory.timestamp)).limit(limit).subquery()

        return self.db.query(ChatHistory).select_entity_from(subquery).order_by(ChatHistory.timestamp).all()
    
    def delete_messages(self, message_ids: List[int], user_id: str) -> int:
        """Soft delete messages (mark as deleted)."""
        updated_count = self.db.query(ChatHistory).filter(
            and_(
                ChatHistory.id.in_(message_ids),
                ChatHistory.user_id == user_id
            )
        ).update({ChatHistory.is_deleted: True}, synchronize_session=False)
        
        self.db.commit()
        return updated_count
    
    def clear_conversation(self, user_id: str, conversation_id: str) -> int:
        """Clear all messages in a conversation."""
        updated_count = self.db.query(ChatHistory).filter(
            and_(
                ChatHistory.user_id == user_id,
                ChatHistory.conversation_id == conversation_id
            )
        ).update({ChatHistory.is_deleted: True}, synchronize_session=False)
        
        self.db.commit()
        
        # Reset conversation message count
        self._update_conversation_message_count(conversation_id, reset=True)
        
        return updated_count
    
    def _update_conversation_message_count(self, conversation_id: str, reset: bool = False):
        """Update message count for a conversation."""
        if reset:
            count = 0
        else:
            count = self.db.query(func.count(ChatHistory.id)).filter(
                and_(
                    ChatHistory.conversation_id == conversation_id,
                    ChatHistory.is_deleted == False
                )
            ).scalar()
        
        self.db.query(Conversation).filter(
            Conversation.conversation_id == conversation_id
        ).update(
            {Conversation.message_count: count, Conversation.updated_at: datetime.utcnow()},
            synchronize_session=False
        )
        self.db.commit()

class ConversationService:
    """Service for handling conversation operations."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_conversation(self, conversation_data: ConversationCreate) -> Conversation:
        """Create a new conversation."""
        # Check if conversation already exists
        existing = self.db.query(Conversation).filter(
            Conversation.conversation_id == conversation_data.conversation_id
        ).first()
        
        if existing:
            return existing
        
        db_conversation = Conversation(
            conversation_id=conversation_data.conversation_id,
            user_id=conversation_data.user_id,
            title=conversation_data.title or "New Conversation"
        )
        self.db.add(db_conversation)
        self.db.commit()
        self.db.refresh(db_conversation)
        return db_conversation
    
    def get_user_conversations(self, user_id: str, skip: int = 0, limit: int = 50) -> Tuple[List[Conversation], int]:
        """Get conversations for a user with pagination."""
        query = self.db.query(Conversation).filter(
            and_(
                Conversation.user_id == user_id,
                Conversation.is_active == True
            )
        ).order_by(desc(Conversation.updated_at))
        
        total_count = query.count()
        conversations = query.offset(skip).limit(limit).all()
        
        return conversations, total_count
    
    def get_conversation(self, conversation_id: str, user_id: str) -> Optional[Conversation]:
        """Get a specific conversation."""
        return self.db.query(Conversation).filter(
            and_(
                Conversation.conversation_id == conversation_id,
                Conversation.user_id == user_id,
                Conversation.is_active == True
            )
        ).first()
    
    def update_conversation(self, conversation_id: str, user_id: str, update_data: ConversationUpdateRequest) -> Optional[Conversation]:
        """Update a conversation."""
        conversation = self.get_conversation(conversation_id, user_id)
        if not conversation:
            return None
        
        if update_data.title is not None:
            conversation.title = update_data.title
        if update_data.is_active is not None:
            conversation.is_active = update_data.is_active
        
        conversation.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(conversation)
        return conversation
    
    def delete_conversation(self, conversation_id: str, user_id: str) -> bool:
        """Soft delete a conversation."""
        updated_count = self.db.query(Conversation).filter(
            and_(
                Conversation.conversation_id == conversation_id,
                Conversation.user_id == user_id
            )
        ).update({Conversation.is_active: False}, synchronize_session=False)
        
        self.db.commit()
        return updated_count > 0
    
    def generate_conversation_id(self) -> str:
        """Generate a unique conversation ID."""
        return str(uuid.uuid4())

class UserService:
    """Service for handling user operations."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_or_get_user(self, user_data: UserCreate) -> User:
        """Create a new user or get existing one."""
        # Check if user already exists
        existing_user = self.db.query(User).filter(
            User.user_id == user_data.user_id
        ).first()
        
        if existing_user:
            # Update last active timestamp
            existing_user.last_active = datetime.utcnow()
            self.db.commit()
            self.db.refresh(existing_user)
            return existing_user
        
        # Create new user
        db_user = User(
            user_id=user_data.user_id,
            username=user_data.username
        )
        self.db.add(db_user)
        self.db.commit()
        self.db.refresh(db_user)
        return db_user
    
    def get_user(self, user_id: str) -> Optional[User]:
        """Get user by user_id."""
        return self.db.query(User).filter(
            and_(
                User.user_id == user_id,
                User.is_active == True
            )
        ).first()
    
    def update_user_activity(self, user_id: str) -> bool:
        """Update user's last active timestamp."""
        updated_count = self.db.query(User).filter(
            User.user_id == user_id
        ).update(
            {User.last_active: datetime.utcnow()},
            synchronize_session=False
        )
        self.db.commit()
        return updated_count > 0

    def register_user(self, user_data: UserRegister) -> User:
        """Register a new user with hashed password."""
        existing = self.db.query(User).filter(
            User.user_id == user_data.user_id
        ).first()
        if existing:
            raise ValueError(f"User '{user_data.user_id}' already exists")

        if user_data.email:
            email_exists = self.db.query(User).filter(
                User.email == user_data.email
            ).first()
            if email_exists:
                raise ValueError("Email already registered")

        db_user = User(
            user_id=user_data.user_id,
            username=user_data.username,
            email=user_data.email,
            password_hash=get_password_hash(user_data.password),
        )
        self.db.add(db_user)
        self.db.commit()
        self.db.refresh(db_user)
        return db_user

    def authenticate_user(self, user_id: str, password: str) -> Optional[User]:
        """Authenticate a user by user_id and password."""
        user = self.db.query(User).filter(
            User.user_id == user_id,
            User.is_active == True,
        ).first()

        if not user or not user.password_hash:
            return None
        if not verify_password(password, user.password_hash):
            return None

        user.last_active = datetime.utcnow()
        self.db.commit()
        self.db.refresh(user)
        return user

class AIService:
    """Service for AI integration with Google Gemini."""
    
    def __init__(self):
        import os
        self.api_key = os.getenv("GEMINI_API_KEY")
        if self.api_key:
            genai.configure(api_key=self.api_key)
            # Use the same model as your Streamlit app
            self.model = genai.GenerativeModel('gemini-2.5-flash')
        else:
            print("Warning: GEMINI_API_KEY not found in environment variables")
            self.model = None
    
    def generate_response(self, user_message: str, conversation_history: List[ChatHistory]) -> str:
        """Generate AI response based on user message and conversation history."""
        if not self.model:
            return "AI service is not configured. Please set GEMINI_API_KEY in your environment."
        
        try:
            # Format conversation history for context
            context = self._format_conversation_for_ai(conversation_history[-10:])  # Last 10 messages for context
            
            # Prepare the prompt with context
            if context:
                prompt = f"""Previous conversation context:
{context}

Current user message: {user_message}

Please provide a helpful and engaging response:"""
            else:
                prompt = user_message
            
            # Generate response using Gemini
            response = self.model.generate_content(prompt)
            return response.text if response.text else "I'm sorry, I couldn't generate a response."
            
        except Exception as e:
            import traceback
            print(f"Error generating AI response: {e}")
            print(f"Traceback: {traceback.format_exc()}")
            return f"I'm sorry, I encountered an error while processing your message. Please try again."
    
    def _format_conversation_for_ai(self, messages: List[ChatHistory]) -> str:
        """Format conversation history for AI context."""
        if not messages:
            return ""
            
        formatted_messages = []
        for msg in messages:
            role = "User" if msg.message_type == MessageType.HUMAN else "Assistant"
            formatted_messages.append(f"{role}: {msg.content}")
        return "\n".join(formatted_messages)
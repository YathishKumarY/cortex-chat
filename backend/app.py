from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Optional
import uvicorn
import os
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from parent directory
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

# Import our modules
from database import get_db, init_db, test_connection
from schemas import (
    ChatRequest, ChatResponse, ChatMessageResponse, ChatMessageCreate,
    ConversationResponse, ConversationCreate, ConversationHistory,
    ConversationListResponse, UserCreate, UserResponse,
    HealthResponse, ErrorResponse, MessageDeleteRequest,
    ConversationUpdateRequest, MessageType,
    UserRegister, UserLogin, Token
)
from services import ChatService, ConversationService, UserService, AIService
from models import ChatHistory, User
from auth import get_current_user, create_access_token

# Initialize FastAPI app
app = FastAPI(
    title="Gemini AI Persistent Chat Backend",
    description="Backend API for Persistent AI Chatbot with PostgreSQL",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this properly for production
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Initialize AI service
ai_service = AIService()

# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize database on startup."""
    try:
        if test_connection():
            init_db()
            print("Database initialized successfully!")
        else:
            print("Warning: Database connection failed during startup!")
    except Exception as e:
        print(f"Error during startup: {e}")

# Health check endpoint (public)
@app.get("/health", response_model=HealthResponse)
async def health_check(db: Session = Depends(get_db)):
    """Health check endpoint."""
    db_connected = True
    try:
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
    except Exception:
        db_connected = False

    return HealthResponse(
        status="healthy" if db_connected else "unhealthy",
        timestamp=datetime.utcnow(),
        database_connected=db_connected
    )

# ==================== Auth Endpoints (public) ====================

@app.post("/auth/register", response_model=Token)
async def register(user_data: UserRegister, db: Session = Depends(get_db)):
    """Register a new user."""
    try:
        user_service = UserService(db)
        user = user_service.register_user(user_data)
        access_token = create_access_token(data={"sub": user.user_id})
        return Token(
            access_token=access_token,
            user_id=user.user_id,
            username=user.username,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")

@app.post("/auth/login", response_model=Token)
async def login(credentials: UserLogin, db: Session = Depends(get_db)):
    """Login and get JWT token."""
    user_service = UserService(db)
    user = user_service.authenticate_user(credentials.user_id, credentials.password)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid user ID or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(data={"sub": user.user_id})
    return Token(
        access_token=access_token,
        user_id=user.user_id,
        username=user.username,
    )

@app.get("/auth/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Get current authenticated user info."""
    return UserResponse.from_orm(current_user)

# ==================== Protected Endpoints ====================

# Chat endpoint
@app.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Handle chat request and generate AI response."""
    try:
        user_id = current_user.user_id
        chat_service = ChatService(db)
        conversation_service = ConversationService(db)

        # Create or get conversation
        conversation_create = ConversationCreate(
            conversation_id=request.conversation_id,
            user_id=user_id,
            title=f"Conversation {request.conversation_id}"
        )
        conversation_service.create_conversation(conversation_create)

        # Add user message to history
        user_message_data = ChatMessageCreate(
            user_id=user_id,
            conversation_id=request.conversation_id,
            message_type=MessageType.HUMAN,
            content=request.message
        )
        user_message = chat_service.add_message(user_message_data)

        # Get conversation history for context
        conversation_history = chat_service.get_recent_messages(
            user_id, request.conversation_id, limit=20
        )

        # Generate AI response
        ai_response_text = ai_service.generate_response(
            request.message, conversation_history
        )

        # Add AI response to history
        ai_message_data = ChatMessageCreate(
            user_id=user_id,
            conversation_id=request.conversation_id,
            message_type=MessageType.AI,
            content=ai_response_text
        )
        ai_message = chat_service.add_message(ai_message_data)

        # Get updated message count
        conversation = conversation_service.get_conversation(
            request.conversation_id, user_id
        )

        return ChatResponse(
            user_message=ChatMessageResponse.from_orm(user_message),
            ai_message=ChatMessageResponse.from_orm(ai_message),
            conversation_id=request.conversation_id,
            message_count=conversation.message_count if conversation else 2
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat processing failed: {str(e)}")

# Conversation history endpoint
@app.get("/conversations/{conversation_id}/history", response_model=ConversationHistory)
async def get_conversation_history(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get full conversation history."""
    try:
        user_id = current_user.user_id
        chat_service = ChatService(db)
        conversation_service = ConversationService(db)

        conversation = conversation_service.get_conversation(conversation_id, user_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        messages = chat_service.get_conversation_history(user_id, conversation_id)

        return ConversationHistory(
            conversation=ConversationResponse.from_orm(conversation),
            messages=[ChatMessageResponse.from_orm(msg) for msg in messages]
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get conversation history: {str(e)}")

# User conversations endpoint
@app.get("/users/{user_id}/conversations", response_model=ConversationListResponse)
async def get_user_conversations(
    user_id: str,
    current_user: User = Depends(get_current_user),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=100, description="Number of records to return"),
    db: Session = Depends(get_db),
):
    """Get all conversations for a user."""
    if user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    try:
        conversation_service = ConversationService(db)
        conversations, total_count = conversation_service.get_user_conversations(
            current_user.user_id, skip, limit
        )

        return ConversationListResponse(
            conversations=[ConversationResponse.from_orm(conv) for conv in conversations],
            total_count=total_count,
            page=skip // limit + 1,
            page_size=limit
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get conversations: {str(e)}")

# Create conversation endpoint
@app.post("/conversations", response_model=ConversationResponse)
async def create_conversation(
    conversation_data: ConversationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new conversation."""
    try:
        conversation_service = ConversationService(db)

        # Override user_id with authenticated user
        conversation_data.user_id = current_user.user_id
        conversation = conversation_service.create_conversation(conversation_data)

        return ConversationResponse.from_orm(conversation)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create conversation: {str(e)}")

# Update conversation endpoint
@app.put("/conversations/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(
    conversation_id: str,
    update_data: ConversationUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update a conversation."""
    try:
        conversation_service = ConversationService(db)
        conversation = conversation_service.update_conversation(
            conversation_id, current_user.user_id, update_data
        )

        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        return ConversationResponse.from_orm(conversation)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update conversation: {str(e)}")

# Delete conversation endpoint
@app.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a conversation."""
    try:
        conversation_service = ConversationService(db)
        success = conversation_service.delete_conversation(conversation_id, current_user.user_id)

        if not success:
            raise HTTPException(status_code=404, detail="Conversation not found")

        return {"message": "Conversation deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete conversation: {str(e)}")

# Clear conversation endpoint
@app.delete("/conversations/{conversation_id}/messages")
async def clear_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Clear all messages in a conversation."""
    try:
        chat_service = ChatService(db)
        deleted_count = chat_service.clear_conversation(current_user.user_id, conversation_id)

        return {"message": f"Cleared {deleted_count} messages from conversation"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear conversation: {str(e)}")

# Delete specific messages endpoint
@app.delete("/messages")
async def delete_messages(
    request: MessageDeleteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete specific messages."""
    try:
        chat_service = ChatService(db)
        deleted_count = chat_service.delete_messages(request.message_ids, current_user.user_id)

        return {"message": f"Deleted {deleted_count} messages"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete messages: {str(e)}")

# Messages endpoint for saving individual messages
@app.post("/messages")
async def save_message(
    request: ChatMessageCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Save an individual message."""
    try:
        chat_service = ChatService(db)
        # Override user_id with authenticated user
        request.user_id = current_user.user_id
        message = chat_service.add_message(request)

        return {
            "id": message.id,
            "message": "Message saved successfully",
            "timestamp": message.timestamp
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error saving message: {str(e)}")

# User endpoints (protected)
@app.post("/users", response_model=UserResponse)
async def create_user(user_data: UserCreate, db: Session = Depends(get_db)):
    """Create or get a user (legacy endpoint)."""
    try:
        user_service = UserService(db)
        user = user_service.create_or_get_user(user_data)
        return UserResponse.from_orm(user)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create user: {str(e)}")

@app.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get user information."""
    if user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return UserResponse.from_orm(current_user)

# Error handler
@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle general exceptions."""
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="Internal server error",
            detail=str(exc),
            timestamp=datetime.utcnow()
        ).dict()
    )

# Run the application
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        log_level="info"
    )

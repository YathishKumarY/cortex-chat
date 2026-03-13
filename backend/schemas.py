from pydantic import BaseModel, Field, validator
from typing import List, Optional, Union
from datetime import datetime
from enum import Enum

class MessageType(str, Enum):
    """Message type enumeration."""
    HUMAN = "Human"
    AI = "AI"

class ChatMessageBase(BaseModel):
    """Base chat message schema."""
    user_id: str = Field(..., min_length=1, max_length=255)
    conversation_id: str = Field(..., min_length=1, max_length=255)
    message_type: MessageType
    content: str = Field(..., min_length=1)

class ChatMessageCreate(ChatMessageBase):
    """Schema for creating a chat message."""
    pass

class ChatMessageResponse(ChatMessageBase):
    """Schema for chat message response."""
    id: int
    timestamp: datetime
    is_deleted: bool = False
    
    class Config:
        orm_mode = True
        from_attributes = True

class ChatRequest(BaseModel):
    """Schema for chat request."""
    user_id: str = Field(..., min_length=1, max_length=255)
    conversation_id: str = Field(..., min_length=1, max_length=255)
    message: str = Field(..., min_length=1)
    
    @validator('message')
    def validate_message(cls, v):
        if not v.strip():
            raise ValueError('Message cannot be empty')
        return v.strip()

class ChatResponse(BaseModel):
    """Schema for chat response."""
    user_message: ChatMessageResponse
    ai_message: ChatMessageResponse
    conversation_id: str
    message_count: int

class ConversationBase(BaseModel):
    """Base conversation schema."""
    conversation_id: str = Field(..., min_length=1, max_length=255)
    user_id: str = Field(..., min_length=1, max_length=255)
    title: Optional[str] = Field(None, max_length=500)

class ConversationCreate(ConversationBase):
    """Schema for creating a conversation."""
    pass

class ConversationResponse(ConversationBase):
    """Schema for conversation response."""
    id: int
    created_at: datetime
    updated_at: datetime
    is_active: bool
    message_count: int
    
    class Config:
        orm_mode = True
        from_attributes = True

class ConversationHistory(BaseModel):
    """Schema for conversation history."""
    conversation: ConversationResponse
    messages: List[ChatMessageResponse]

class UserBase(BaseModel):
    """Base user schema."""
    user_id: str = Field(..., min_length=1, max_length=255)
    username: str = Field(..., min_length=1, max_length=255)

class UserCreate(UserBase):
    """Schema for creating a user."""
    pass

class UserResponse(UserBase):
    """Schema for user response."""
    id: int
    created_at: datetime
    last_active: datetime
    is_active: bool
    
    class Config:
        orm_mode = True
        from_attributes = True

class ConversationListResponse(BaseModel):
    """Schema for conversation list response."""
    conversations: List[ConversationResponse]
    total_count: int
    page: int
    page_size: int

class HealthResponse(BaseModel):
    """Schema for health check response."""
    status: str
    timestamp: datetime
    database_connected: bool
    version: str = "1.0.0"

class ErrorResponse(BaseModel):
    """Schema for error response."""
    error: str
    detail: Optional[str] = None
    timestamp: datetime

class MessageDeleteRequest(BaseModel):
    """Schema for deleting messages."""
    message_ids: List[int] = Field(..., min_items=1)

class ConversationUpdateRequest(BaseModel):
    """Schema for updating conversation."""
    title: Optional[str] = Field(None, max_length=500)
    is_active: Optional[bool] = None

# Authentication schemas

class UserRegister(BaseModel):
    """Schema for user registration."""
    user_id: str = Field(..., min_length=1, max_length=255)
    username: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=6, max_length=128)
    email: Optional[str] = Field(None, max_length=255)

class UserLogin(BaseModel):
    """Schema for user login."""
    user_id: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=1)

class Token(BaseModel):
    """Schema for JWT token response."""
    access_token: str
    token_type: str = "bearer"
    user_id: str
    username: str

class TokenData(BaseModel):
    """Schema for token payload data."""
    user_id: Optional[str] = None
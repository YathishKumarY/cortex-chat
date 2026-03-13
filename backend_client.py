"""
Backend API Client for Streamlit Frontend

This module handles all API calls to the FastAPI backend for persistent storage.
"""

import requests
import streamlit as st
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import json
import uuid

class BackendClient:
    """Client for interacting with the FastAPI backend."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        
        # Test backend connection
        if not self._test_connection():
            st.warning("⚠️ Backend server is not running. Chat history will not be saved.")
            self.connected = False
        else:
            self.connected = True
    
    def _test_connection(self) -> bool:
        """Test if backend is accessible."""
        try:
            response = self.session.get(f"{self.base_url}/health", timeout=2)
            return response.status_code == 200
        except:
            return False
    
    def ensure_user(self, username: str) -> Optional[str]:
        """Ensure user exists in backend, create if needed."""
        if not self.connected:
            return None
            
        try:
            # Use consistent user_id based on username
            user_id = f"streamlit_{username}"
            
            # Try to create user (will return existing if already exists)
            data = {
                "user_id": user_id,
                "username": username
            }
            response = self.session.post(f"{self.base_url}/users", json=data, timeout=5)
            
            if response.status_code == 200:
                user_data = response.json()
                return user_data["user_id"]
            return None
            
        except Exception as e:
            st.error(f"Error ensuring user: {e}")
            return None
    
    def get_or_create_conversation(self, user_id: str, conversation_id: str = None, title: str = "Streamlit Chat") -> Optional[str]:
        """Get existing conversation or create new one."""
        if not self.connected or not user_id:
            return None
            
        if conversation_id:
            # Check if conversation exists
            try:
                params = {"user_id": user_id}
                response = self.session.get(
                    f"{self.base_url}/conversations/{conversation_id}/history",
                    params=params,
                    timeout=5
                )
                if response.status_code == 200:
                    return conversation_id
            except:
                pass
        
        # Create new conversation
        return self.create_conversation(user_id, title)
    
    def create_conversation(self, user_id: str, title: str = "New Chat") -> Optional[str]:
        """Create a new conversation in the backend."""
        if not self.connected or not user_id:
            return None
            
        try:
            # Generate a unique conversation ID
            conversation_id = str(uuid.uuid4())
            
            data = {
                "conversation_id": conversation_id,
                "user_id": user_id,
                "title": title
            }
            
            response = self.session.post(
                f"{self.base_url}/conversations",
                json=data,
                timeout=10
            )
            
            if response.status_code == 200:
                response_data = response.json()
                return response_data["conversation_id"]
            return None
            
        except Exception as e:
            st.error(f"Error creating conversation: {e}")
            return None
    
    def get_conversation_messages_formatted(self, user_id: str, conversation_id: str) -> List[Dict]:
        """Get conversation history formatted for Streamlit chat interface."""
        if not self.connected or not user_id or not conversation_id:
            return []
            
        try:
            params = {"user_id": user_id}
            response = self.session.get(
                f"{self.base_url}/conversations/{conversation_id}/history",
                params=params,
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                messages = data.get("messages", [])
                
                # Convert to Streamlit format
                formatted_messages = []
                for msg in messages:
                    if msg["message_type"] == "Human":
                        formatted_messages.append({
                            "role": "user",
                            "content": msg["content"]
                        })
                    else:
                        formatted_messages.append({
                            "role": "model", 
                            "content": msg["content"],
                            "avatar": "🤖"
                        })
                
                return formatted_messages
            return []
            
        except Exception as e:
            st.error(f"Error getting formatted conversation history: {e}")
            return []
    
    def get_user_conversation_list(self, user_id: str) -> Dict[str, str]:
        """Get user's conversations as dict mapping conversation_id -> title.

        Rationale: The Streamlit UI logic treats keys as stable internal IDs. Returning
        IDs as keys prevents ambiguity when two conversations share a title and avoids
        costly reverse lookups. A compatibility layer in get_conversations_from_backend
        will invert if an older mapping is encountered.
        """
        if not self.connected or not user_id:
            return {"NEW_CHAT": "New Chat"}

        try:
            response = self.session.get(
                f"{self.base_url}/users/{user_id}/conversations",
                timeout=5
            )

            if response.status_code == 200:
                data = response.json()
                conversations = data.get("conversations", [])

                conv_dict = {"NEW_CHAT": "New Chat"}
                for conv in conversations:
                    cid = conv.get("conversation_id")
                    if not cid:
                        continue
                    title = conv.get("title") or f"Conversation {cid[:8]}"
                    conv_dict[cid] = title
                return conv_dict
            return {"NEW_CHAT": "New Chat"}
        except Exception as e:
            st.error(f"Error getting conversations: {e}")
            return {"NEW_CHAT": "New Chat"}
    
    def save_message_pair(self, user_id: str, conversation_id: str, user_message: str, ai_response: str) -> bool:
        """Save both user message and AI response to backend."""
        if not self.connected or not user_id or not conversation_id:
            return False
            
        try:
            # Create user message
            user_data = {
                "user_id": user_id,
                "conversation_id": conversation_id,
                "message_type": "Human",
                "content": user_message
            }
            
            # Create AI message  
            ai_data = {
                "user_id": user_id,
                "conversation_id": conversation_id,
                "message_type": "AI", 
                "content": ai_response
            }
            
            # Save user message
            response1 = self.session.post(f"{self.base_url}/messages", json=user_data, timeout=5)
            # Save AI response
            response2 = self.session.post(f"{self.base_url}/messages", json=ai_data, timeout=5)
            
            return response1.status_code == 200 and response2.status_code == 200
            
        except Exception as e:
            st.error(f"Error saving message pair: {e}")
            return False
        """Create a new conversation."""
        if not self.connected or not user_id:
            return None
            
        try:
            conversation_id = f"conv_{int(datetime.now().timestamp())}_{str(uuid.uuid4())[:8]}"
            
            data = {
                "user_id": user_id,
                "conversation_id": conversation_id,
                "title": title
            }
            response = self.session.post(f"{self.base_url}/conversations", json=data, timeout=5)
            
            if response.status_code == 200:
                return conversation_id
            return None
            
        except Exception as e:
            st.error(f"Error creating conversation: {e}")
            return None
    
    def send_message(self, user_id: str, conversation_id: str, message: str) -> Optional[Dict]:
        """Send a message and get AI response."""
        if not self.connected or not user_id or not conversation_id:
            return None
            
        try:
            data = {
                "user_id": user_id,
                "conversation_id": conversation_id,
                "message": message
            }
            response = self.session.post(f"{self.base_url}/chat", json=data, timeout=30)
            
            if response.status_code == 200:
                return response.json()
            return None
            
        except Exception as e:
            st.error(f"Error sending message to backend: {e}")
            return None
    
    def get_conversation_history(self, user_id: str, conversation_id: str) -> List[Dict]:
        """Get conversation history."""
        if not self.connected or not user_id or not conversation_id:
            return []
            
        try:
            params = {"user_id": user_id}
            response = self.session.get(
                f"{self.base_url}/conversations/{conversation_id}/history",
                params=params,
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("messages", [])
            return []
            
        except Exception as e:
            st.error(f"Error getting conversation history: {e}")
            return []
    
    def get_user_conversations(self, user_id: str) -> List[Dict]:
        """Get user's conversations."""
        if not self.connected or not user_id:
            return []
            
        try:
            response = self.session.get(
                f"{self.base_url}/users/{user_id}/conversations",
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("conversations", [])
            return []
            
        except Exception as e:
            st.error(f"Error getting conversations: {e}")
            return []

# Global backend client instance
@st.cache_resource
def get_backend_client():
    """Get cached backend client instance."""
    return BackendClient()

def init_user_session(username: str) -> Tuple[Optional[str], Optional[str]]:
    """Initialize user session with backend."""
    client = get_backend_client()
    
    # Ensure user exists
    user_id = client.ensure_user(username)
    return user_id, None  # Don't create conversation here, let user choose

def get_or_create_conversation_session(user_id: str, selected_chat: str, past_chats: Dict[str, str]) -> Optional[str]:
    """Get or create conversation based on user selection."""
    client = get_backend_client()
    
    if selected_chat == "New Chat":
        # Create new conversation
        title = f"Chat Session - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        conversation_id = client.create_conversation(user_id, title)
        if conversation_id:
            # Update past_chats dict
            past_chats[conversation_id] = title
        return conversation_id
    else:
        # Get existing conversation ID
        return past_chats.get(selected_chat)

def load_messages_from_backend(user_id: str, conversation_id: str) -> List[Dict]:
    """Load messages from backend for Streamlit interface."""
    client = get_backend_client()
    return client.get_conversation_messages_formatted(user_id, conversation_id)

def save_message_pair_to_backend(user_id: str, conversation_id: str, user_message: str, ai_response: str) -> bool:
    """Save both user and AI messages to backend."""
    client = get_backend_client()
    return client.save_message_pair(user_id, conversation_id, user_message, ai_response)

def get_conversations_from_backend(user_id: str) -> Dict[str, str]:
    """Get user's conversations from backend.

    Returns a mapping of conversation_id -> title (normalized for frontend).
    Legacy code previously assumed title -> id; this function now guarantees
    the canonical direction expected by the Streamlit UI (keys are IDs).
    """
    client = get_backend_client()
    raw = client.get_user_conversation_list(user_id)
    # New implementation of get_user_conversation_list (below) will already
    # return id->title, but keep a defensive normalization in case of mixed versions.
    # If keys look like titles and values look like UUIDs, invert.
    try:
        if raw:
            sample_key, sample_val = next(iter(raw.items()))
            import re
            uuid_pattern = re.compile(r"^[0-9a-fA-F-]{36}$")
            if uuid_pattern.match(sample_val) and not uuid_pattern.match(sample_key):
                # Likely old style mapping title -> id; invert
                return {v: k for k, v in raw.items()}
    except Exception:
        pass
    return raw

def delete_conversation_from_backend(user_id: str, conversation_id: str) -> bool:
    """Delete a conversation from backend."""
    client = get_backend_client()
    try:
        response = client.session.delete(
            f"{client.base_url}/conversations/{conversation_id}",
            params={"user_id": user_id}
        )
        return response.status_code == 200
    except Exception:
        return False
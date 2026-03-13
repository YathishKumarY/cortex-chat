import requests
import json
import streamlit as st
import time
import os
from typing import List, Dict, Optional, Any


class GeminiAPIClient:
    """Client for communicating with the Gemini Chat Backend API"""

    def __init__(self, base_url: str = None):
        self.base_url = base_url or os.getenv("BACKEND_URL", "http://localhost:8000")
        self.session = requests.Session()
        self.token = None

    def set_token(self, token: str):
        """Set JWT token for authenticated requests."""
        self.token = token
        self.session.headers["Authorization"] = f"Bearer {token}"

    def clear_token(self):
        """Remove JWT token."""
        self.token = None
        self.session.headers.pop("Authorization", None)

    def health_check(self) -> bool:
        """Check if the backend API is healthy"""
        try:
            response = self.session.get(f"{self.base_url}/health", timeout=5)
            return response.status_code == 200
        except:
            return False

    # ==================== Auth Methods ====================

    def register(self, user_id: str, username: str, password: str, email: Optional[str] = None) -> Dict[str, Any]:
        """Register a new user and get JWT token."""
        data = {"user_id": user_id, "username": username, "password": password}
        if email:
            data["email"] = email
        try:
            response = self.session.post(f"{self.base_url}/auth/register", json=data, timeout=10)
            if response.status_code == 400:
                return {"error": response.json().get("detail", "Registration failed")}
            response.raise_for_status()
            result = response.json()
            if "access_token" in result:
                self.set_token(result["access_token"])
            return result
        except requests.exceptions.RequestException as e:
            return {"error": str(e)}

    def login(self, user_id: str, password: str) -> Dict[str, Any]:
        """Login and get JWT token."""
        data = {"user_id": user_id, "password": password}
        try:
            response = self.session.post(f"{self.base_url}/auth/login", json=data, timeout=10)
            if response.status_code == 401:
                return {"error": "Invalid user ID or password"}
            response.raise_for_status()
            result = response.json()
            if "access_token" in result:
                self.set_token(result["access_token"])
            return result
        except requests.exceptions.RequestException as e:
            return {"error": str(e)}

    def get_me(self) -> Dict[str, Any]:
        """Get current authenticated user info."""
        try:
            response = self.session.get(f"{self.base_url}/auth/me", timeout=5)
            if response.status_code == 401:
                return {}
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException:
            return {}

    # ==================== User Methods ====================

    def get_user(self, user_id: str) -> Dict[str, Any]:
        """Get user by ID"""
        try:
            response = self.session.get(f"{self.base_url}/users/{user_id}")
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            st.error(f"Failed to get user: {e}")
            return {}

    def get_user_conversations(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all conversations for a user"""
        try:
            response = self.session.get(
                f"{self.base_url}/users/{user_id}/conversations"
            )
            response.raise_for_status()
            result = response.json()
            # API returns {"conversations": [...], "total_count": ...}
            if isinstance(result, dict):
                return result.get("conversations", [])
            return result
        except requests.exceptions.RequestException as e:
            st.error(f"Failed to get conversations: {e}")
            return []

    def get_conversation_messages(self, conversation_id: str) -> List[Dict[str, Any]]:
        """Get all messages in a conversation"""
        try:
            response = self.session.get(
                f"{self.base_url}/conversations/{conversation_id}/history",
            )
            response.raise_for_status()
            result = response.json()
            return result.get("messages", [])
        except requests.exceptions.RequestException as e:
            st.error(f"Failed to get messages: {e}")
            return []

    def send_chat_message(
        self, user_id: str, message: str, conversation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send a chat message and get AI response"""
        data = {"user_id": user_id, "message": message}
        if conversation_id:
            data["conversation_id"] = conversation_id

        try:
            response = self.session.post(f"{self.base_url}/chat", json=data)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            st.error(f"Failed to send message: {e}")
            return {}

    def upload_file(
        self,
        user_id: str,
        file_content: bytes,
        filename: str,
        conversation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Upload a file and optionally attach to conversation"""
        files = {"file": (filename, file_content)}
        data = {"user_id": user_id}
        if conversation_id:
            data["conversation_id"] = conversation_id

        try:
            response = self.session.post(
                f"{self.base_url}/upload", files=files, data=data
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            st.error(f"Failed to upload file: {e}")
            return {}

    def create_conversation(self, user_id: str, title: str, conversation_id: Optional[str] = None) -> Dict[str, Any]:
        """Create a new conversation"""
        if not conversation_id:
            conversation_id = f"{user_id}_{int(time.time())}"
        data = {"user_id": user_id, "conversation_id": conversation_id, "title": title}
        try:
            response = self.session.post(
                f"{self.base_url}/conversations", json=data
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            st.error(f"Failed to create conversation: {e}")
            return {}

    def delete_conversation(self, conversation_id: str, user_id: str) -> bool:
        """Delete a conversation"""
        try:
            response = self.session.delete(
                f"{self.base_url}/conversations/{conversation_id}",
            )
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            st.error(f"Failed to delete conversation: {e}")
            return False

    def update_conversation(self, conversation_id: str, title: str) -> bool:
        """Update a conversation title"""
        try:
            response = self.session.put(
                f"{self.base_url}/conversations/{conversation_id}",
                json={"title": title},
            )
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            st.error(f"Failed to update conversation: {e}")
            return False


def get_api_client():
    """Get API client instance per session (not shared across users)."""
    if "api_client" not in st.session_state:
        st.session_state.api_client = GeminiAPIClient()
    client = st.session_state.api_client
    # Ensure token is set from session state
    token = st.session_state.get("jwt_token")
    if token and not client.token:
        client.set_token(token)
    return client


def get_conversation_summary(messages: List[Dict[str, Any]]) -> str:
    """Generate a conversation summary from messages"""
    if not messages:
        return "New Chat"

    # Get the first user message for summary
    for msg in messages:
        if msg.get("role") == "user" and msg.get("content"):
            content = msg["content"][:50]
            if len(msg["content"]) > 50:
                content += "..."
            return content

    return "New Chat"

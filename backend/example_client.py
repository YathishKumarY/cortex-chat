#!/usr/bin/env python3
"""
Example client for testing the Persistent AI Chatbot Backend API.

This script demonstrates how to interact with the FastAPI backend.
"""

import requests
import json
from datetime import datetime
from typing import Dict, List, Optional

class ChatbotClient:
    """Client for interacting with the Chatbot API."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
    
    def health_check(self) -> Dict:
        """Check if the API is healthy."""
        response = self.session.get(f"{self.base_url}/health")
        response.raise_for_status()
        return response.json()
    
    def create_user(self, user_id: str, username: str) -> Dict:
        """Create a new user."""
        data = {
            "user_id": user_id,
            "username": username
        }
        response = self.session.post(f"{self.base_url}/users", json=data)
        response.raise_for_status()
        return response.json()
    
    def create_conversation(self, user_id: str, conversation_id: str, title: str = None) -> Dict:
        """Create a new conversation."""
        data = {
            "user_id": user_id,
            "conversation_id": conversation_id,
            "title": title or f"Conversation {conversation_id}"
        }
        response = self.session.post(f"{self.base_url}/conversations", json=data)
        response.raise_for_status()
        return response.json()
    
    def send_message(self, user_id: str, conversation_id: str, message: str) -> Dict:
        """Send a message and get AI response."""
        data = {
            "user_id": user_id,
            "conversation_id": conversation_id,
            "message": message
        }
        response = self.session.post(f"{self.base_url}/chat", json=data)
        response.raise_for_status()
        return response.json()
    
    def get_conversation_history(self, conversation_id: str, user_id: str) -> Dict:
        """Get conversation history."""
        params = {"user_id": user_id}
        response = self.session.get(
            f"{self.base_url}/conversations/{conversation_id}/history",
            params=params
        )
        response.raise_for_status()
        return response.json()
    
    def get_user_conversations(self, user_id: str, skip: int = 0, limit: int = 10) -> Dict:
        """Get user's conversations."""
        params = {"skip": skip, "limit": limit}
        response = self.session.get(
            f"{self.base_url}/users/{user_id}/conversations",
            params=params
        )
        response.raise_for_status()
        return response.json()
    
    def clear_conversation(self, conversation_id: str, user_id: str) -> Dict:
        """Clear all messages in a conversation."""
        params = {"user_id": user_id}
        response = self.session.delete(
            f"{self.base_url}/conversations/{conversation_id}/messages",
            params=params
        )
        response.raise_for_status()
        return response.json()
    
    def delete_conversation(self, conversation_id: str, user_id: str) -> Dict:
        """Delete a conversation."""
        params = {"user_id": user_id}
        response = self.session.delete(
            f"{self.base_url}/conversations/{conversation_id}",
            params=params
        )
        response.raise_for_status()
        return response.json()

def main():
    """Example usage of the ChatbotClient."""
    client = ChatbotClient()
    
    print("🤖 Persistent AI Chatbot - API Client Example")
    print("=" * 50)
    
    try:
        # 1. Health check
        print("\n1. Checking API health...")
        health = client.health_check()
        print(f"   Status: {health['status']}")
        print(f"   Database: {'✅ Connected' if health['database_connected'] else '❌ Disconnected'}")
        
        # 2. Create user
        print("\n2. Creating user...")
        user_id = "example_user_001"
        username = "Example User"
        user = client.create_user(user_id, username)
        print(f"   User created: {user['username']} ({user['user_id']})")
        
        # 3. Create conversation
        print("\n3. Creating conversation...")
        conversation_id = f"conv_{int(datetime.now().timestamp())}"
        conversation = client.create_conversation(
            user_id, conversation_id, "Example Conversation"
        )
        print(f"   Conversation created: {conversation['title']}")
        
        # 4. Send messages
        print("\n4. Sending messages...")
        messages = [
            "Hello! Can you introduce yourself?",
            "What can you help me with?",
            "Tell me about artificial intelligence."
        ]
        
        for i, message in enumerate(messages, 1):
            print(f"\n   Message {i}: {message}")
            response = client.send_message(user_id, conversation_id, message)
            ai_response = response['ai_message']['content']
            print(f"   AI Response: {ai_response[:100]}{'...' if len(ai_response) > 100 else ''}")
        
        # 5. Get conversation history
        print("\n5. Getting conversation history...")
        history = client.get_conversation_history(conversation_id, user_id)
        messages_count = len(history['messages'])
        print(f"   Total messages in conversation: {messages_count}")
        
        # 6. Get user conversations
        print("\n6. Getting user conversations...")
        conversations = client.get_user_conversations(user_id)
        conv_count = conversations['total_count']
        print(f"   Total conversations for user: {conv_count}")
        
        # 7. Optional: Clear conversation
        clear_conv = input("\n7. Clear conversation? (y/N): ").lower().strip()
        if clear_conv in ['y', 'yes']:
            result = client.clear_conversation(conversation_id, user_id)
            print(f"   {result['message']}")
        
        print("\n✅ Example completed successfully!")
        
    except requests.exceptions.RequestException as e:
        print(f"\n❌ API Error: {e}")
        if hasattr(e.response, 'text'):
            print(f"   Response: {e.response.text}")
    except Exception as e:
        print(f"\n❌ Error: {e}")
    
    print("\n" + "=" * 50)
    print("API Documentation: http://localhost:8000/docs")
    print("Health Check: http://localhost:8000/health")

if __name__ == "__main__":
    main()
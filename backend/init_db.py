#!/usr/bin/env python3
"""
Database initialization script for the Persistent AI Chatbot Backend.

This script creates the database tables and sets up initial data.
"""

import sys
import os
from pathlib import Path

# Add the backend directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from database import engine, SessionLocal, test_connection, init_db, drop_db
from models import Base, User, Conversation, ChatHistory
from sqlalchemy import text

def create_indexes():
    """Create additional database indexes for better performance."""
    with engine.connect() as connection:
        # Create indexes that might not be auto-created
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_chat_history_timestamp_desc ON chat_history (timestamp DESC);",
            "CREATE INDEX IF NOT EXISTS idx_conversations_updated_desc ON conversations (updated_at DESC);",
            "CREATE INDEX IF NOT EXISTS idx_users_last_active ON users (last_active DESC);",
        ]
        
        for index_sql in indexes:
            try:
                connection.execute(text(index_sql))
                print(f"Created index: {index_sql[:50]}...")
            except Exception as e:
                print(f"Index creation skipped (may already exist): {e}")
        
        connection.commit()

def create_sample_data():
    """Create sample data for testing (optional)."""
    db = SessionLocal()
    try:
        # Check if sample data already exists
        existing_user = db.query(User).filter(User.user_id == "sample_user").first()
        if existing_user:
            print("Sample data already exists, skipping...")
            return
        
        # Create sample user
        sample_user = User(
            user_id="sample_user",
            username="Sample User"
        )
        db.add(sample_user)
        
        # Create sample conversation
        sample_conversation = Conversation(
            conversation_id="sample_conversation_1",
            user_id="sample_user",
            title="Welcome Conversation",
            message_count=2
        )
        db.add(sample_conversation)
        
        # Create sample chat messages
        sample_messages = [
            ChatHistory(
                user_id="sample_user",
                conversation_id="sample_conversation_1",
                message_type="Human",
                content="Hello! How can you help me today?"
            ),
            ChatHistory(
                user_id="sample_user",
                conversation_id="sample_conversation_1",
                message_type="AI",
                content="Hello! I'm an AI assistant powered by Google's Gemini AI. I can help you with various tasks including answering questions, creative writing, analysis, and much more. What would you like to know or discuss?"
            )
        ]
        
        for message in sample_messages:
            db.add(message)
        
        db.commit()
        print("Sample data created successfully!")
        
    except Exception as e:
        db.rollback()
        print(f"Error creating sample data: {e}")
    finally:
        db.close()

def main():
    """Main initialization function."""
    print("=" * 50)
    print("Persistent AI Chatbot - Database Initialization")
    print("=" * 50)
    
    # Test database connection
    print("\n1. Testing database connection...")
    if not test_connection():
        print("❌ Database connection failed! Please check your configuration.")
        sys.exit(1)
    print("✅ Database connection successful!")
    
    # Create tables
    print("\n2. Creating database tables...")
    try:
        init_db()
        print("✅ Database tables created successfully!")
    except Exception as e:
        print(f"❌ Error creating tables: {e}")
        sys.exit(1)
    
    # Create additional indexes
    print("\n3. Creating database indexes...")
    try:
        create_indexes()
        print("✅ Database indexes created successfully!")
    except Exception as e:
        print(f"⚠️  Warning: Some indexes might not have been created: {e}")
    
    # Ask if user wants sample data
    create_samples = input("\n4. Create sample data for testing? (y/N): ").lower().strip()
    if create_samples in ['y', 'yes']:
        create_sample_data()
    
    print("\n" + "=" * 50)
    print("🎉 Database initialization completed successfully!")
    print("\nNext steps:")
    print("1. Start the FastAPI server: python app.py")
    print("2. Visit http://localhost:8000/docs for API documentation")
    print("3. Test the health endpoint: http://localhost:8000/health")
    print("=" * 50)

if __name__ == "__main__":
    main()
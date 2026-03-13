-- SQL script to create tables manually in pgAdmin
-- Run this in pgAdmin's Query Tool for the 'chatdb' database

-- Create users table
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_active TIMESTAMPTZ DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE
);

-- Create indexes for users table
CREATE INDEX idx_users_user_id ON users(user_id);

-- Create conversations table
CREATE TABLE conversations (
    id SERIAL PRIMARY KEY,
    conversation_id VARCHAR(255) UNIQUE NOT NULL,
    user_id VARCHAR(255) NOT NULL,
    title VARCHAR(500),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE,
    message_count INTEGER DEFAULT 0
);

-- Create indexes for conversations table
CREATE INDEX idx_conversations_conversation_id ON conversations(conversation_id);
CREATE INDEX idx_conversations_user_id ON conversations(user_id);

-- Create chat_history table
CREATE TABLE chat_history (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    conversation_id VARCHAR(255) NOT NULL,
    message_type VARCHAR(50) NOT NULL,
    content TEXT NOT NULL,
    timestamp TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    is_deleted BOOLEAN DEFAULT FALSE NOT NULL
);

-- Create indexes for chat_history table
CREATE INDEX idx_chat_history_user_id ON chat_history(user_id);
CREATE INDEX idx_chat_history_conversation_id ON chat_history(conversation_id);
CREATE INDEX idx_chat_history_user_conversation ON chat_history(user_id, conversation_id);
CREATE INDEX idx_chat_history_timestamp ON chat_history(timestamp);

-- Create alembic_version table for migration tracking
CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL,
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Insert initial migration version
INSERT INTO alembic_version (version_num) VALUES ('001');
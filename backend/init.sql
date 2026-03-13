-- Initial database setup for Persistent AI Chatbot
-- This file is executed when PostgreSQL container starts for the first time

-- Create the main database (if not exists)
CREATE DATABASE chatdb;

-- Connect to the chatdb database
\c chatdb;

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Create custom functions for better search
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create initial indexes for better performance
-- (These will be created by SQLAlchemy but having them here ensures they exist)
COMMENT ON DATABASE chatdb IS 'Database for Persistent AI Chatbot application';

-- Grant permissions (adjust as needed for your security requirements)
-- GRANT ALL PRIVILEGES ON DATABASE chatdb TO your_app_user;
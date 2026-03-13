#!/usr/bin/env python3
"""
Start script for the Persistent AI Chatbot Backend.

This script sets up the database, runs migrations, and starts the FastAPI server.
"""

import subprocess
import sys
import os
from pathlib import Path
from dotenv import load_dotenv
import time
import uvicorn
import psycopg2
from psycopg2 import OperationalError

# Load environment variables from parent directory
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

def main():
    """Start the FastAPI application."""
    # Get configuration from environment variables
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))
    debug = os.getenv("DEBUG", "True").lower() == "true"
    log_level = os.getenv("LOG_LEVEL", "info").lower()
    
    print("=" * 50)
    print("🚀 Starting Persistent AI Chatbot Backend")
    print("=" * 50)
    print(f"Host: {host}")
    print(f"Port: {port}")
    print(f"Debug: {debug}")
    print(f"Log Level: {log_level}")
    print("\nAPI Documentation: http://localhost:8000/docs")
    print("Health Check: http://localhost:8000/health")
    print("=" * 50)
    
    # Start the server
    uvicorn.run(
        "app:app",
        host=host,
        port=port,
        reload=debug,
        log_level=log_level,
        access_log=True
    )

if __name__ == "__main__":
    main()
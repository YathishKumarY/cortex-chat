#!/bin/bash

# Setup script for Persistent AI Chatbot Backend
# This script sets up the development environment

set -e  # Exit on any error

echo "==========================================="
echo "🚀 Setting up Persistent AI Chatbot Backend"
echo "==========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    print_error "Python 3 is not installed. Please install Python 3.10 or higher."
    exit 1
fi

# Check Python version
PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
REQUIRED_VERSION="3.10"
if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    print_error "Python $PYTHON_VERSION is installed, but Python $REQUIRED_VERSION or higher is required."
    exit 1
fi
print_status "Python $PYTHON_VERSION detected"

# Check if PostgreSQL is available
if command -v psql &> /dev/null; then
    print_status "PostgreSQL client detected"
else
    print_warning "PostgreSQL client not found. You'll need PostgreSQL for the database."
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    print_info "Creating Python virtual environment..."
    python3 -m venv venv
    print_status "Virtual environment created"
else
    print_info "Virtual environment already exists"
fi

# Activate virtual environment
print_info "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
print_info "Upgrading pip..."
pip install --upgrade pip
print_status "Pip upgraded"

# Install dependencies
print_info "Installing Python dependencies..."
pip install -r requirements.txt
print_status "Dependencies installed"

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    print_info "Creating .env file from template..."
    cp .env.example .env
    print_warning "Please edit .env file with your actual configuration values"
    print_info "Required variables:"
    echo "  - POSTGRES_PASSWORD: Your PostgreSQL password"
    echo "  - GOOGLE_API_KEY: Your Google Generative AI API key"
else
    print_info ".env file already exists"
fi

# Check if Docker is available for optional database setup
if command -v docker &> /dev/null; then
    print_status "Docker detected - you can use 'docker-compose up -d postgres' for database"
else
    print_info "Docker not found - you'll need to install PostgreSQL manually"
fi

# Ask about database setup
echo ""
print_info "Database setup options:"
echo "1. Use Docker Compose (recommended): docker-compose up -d postgres"
echo "2. Use local PostgreSQL: Install PostgreSQL and create 'chatdb' database"
echo "3. Skip database setup for now"
echo ""
read -p "Choose an option (1-3): " db_choice

case $db_choice in
    1)
        if command -v docker-compose &> /dev/null; then
            print_info "Starting PostgreSQL with Docker Compose..."
            docker-compose up -d postgres
            print_status "PostgreSQL started with Docker"
        else
            print_error "Docker Compose not found. Please install Docker and Docker Compose."
        fi
        ;;
    2)
        print_info "Please ensure PostgreSQL is running and create the database:"
        echo "  createdb chatdb"
        echo "  Or using psql: CREATE DATABASE chatdb;"
        ;;
    3)
        print_warning "Skipping database setup"
        ;;
    *)
        print_warning "Invalid choice. Skipping database setup."
        ;;
esac

# Wait a moment for database to be ready if using Docker
if [ "$db_choice" = "1" ]; then
    print_info "Waiting for database to be ready..."
    sleep 5
fi

# Ask about database initialization
if [ "$db_choice" != "3" ]; then
    echo ""
    read -p "Initialize database tables? (y/N): " init_db
    if [[ $init_db =~ ^[Yy]$ ]]; then
        print_info "Initializing database..."
        python init_db.py
        print_status "Database initialized"
    fi
fi

# Make scripts executable
chmod +x start.py
chmod +x init_db.py

echo ""
echo "==========================================="
print_status "Setup completed successfully!"
echo "==========================================="
echo ""
print_info "Next steps:"
echo "1. Edit .env file with your configuration"
echo "2. Ensure PostgreSQL is running"
echo "3. Start the server: python start.py"
echo "4. Visit http://localhost:8000/docs for API documentation"
echo "5. Test health endpoint: http://localhost:8000/health"
echo ""
print_info "Useful commands:"
echo "  - Start server: python start.py"
echo "  - Initialize DB: python init_db.py"
echo "  - Docker setup: docker-compose up -d"
echo "  - View logs: docker-compose logs -f backend"
echo "==========================================="
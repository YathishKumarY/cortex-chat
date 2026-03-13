# Persistent AI Chatbot Backend

A FastAPI-based backend for a persistent AI chatbot with PostgreSQL storage and Google Generative AI integration.

## Features

- **RESTful API**: Full REST API for chat operations
- **Persistent Storage**: PostgreSQL database for conversation history
- **Memory-Powered Conversations**: Context-aware responses using conversation history
- **User Management**: Multi-user support with conversation tracking
- **Conversation Management**: Create, read, update, delete conversations
- **Message Management**: Store, retrieve, and delete individual messages
- **AI Integration**: Ready for Google Generative AI integration
- **FastAPI Documentation**: Automatic API documentation with Swagger UI
- **Database Migrations**: Alembic integration for schema management

## Quick Start

### Prerequisites

- Python 3.10+
- PostgreSQL 12+
- Google Generative AI API key

### Installation

1. **Navigate to backend directory**:

   ```bash
   cd backend
   ```

2. **Install dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**:

   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

4. **Initialize database**:

   ```bash
   python init_db.py
   ```

5. **Start the server**:
   ```bash
   python start.py
   ```

### API Documentation

Once the server is running, visit:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health

## API Endpoints

### Chat Operations

- `POST /chat` - Send a message and get AI response
- `GET /conversations/{conversation_id}/history` - Get conversation history
- `DELETE /conversations/{conversation_id}/messages` - Clear conversation
- `DELETE /messages` - Delete specific messages

### Conversation Management

- `POST /conversations` - Create new conversation
- `GET /users/{user_id}/conversations` - Get user's conversations
- `PUT /conversations/{conversation_id}` - Update conversation
- `DELETE /conversations/{conversation_id}` - Delete conversation

### User Management

- `POST /users` - Create or get user
- `GET /users/{user_id}` - Get user information

### System

- `GET /health` - Health check endpoint

## Database Schema

### Tables

1. **chat_history** - Stores all chat messages

   - `id` - Primary key
   - `user_id` - User identifier
   - `conversation_id` - Conversation identifier
   - `message_type` - 'Human' or 'AI'
   - `content` - Message content
   - `timestamp` - Message timestamp
   - `is_deleted` - Soft delete flag

2. **conversations** - Tracks conversation metadata

   - `id` - Primary key
   - `conversation_id` - Unique conversation identifier
   - `user_id` - Owner user identifier
   - `title` - Conversation title
   - `created_at` - Creation timestamp
   - `updated_at` - Last update timestamp
   - `is_active` - Active status
   - `message_count` - Number of messages

3. **users** - User information
   - `id` - Primary key
   - `user_id` - Unique user identifier
   - `username` - Display name
   - `created_at` - Registration timestamp
   - `last_active` - Last activity timestamp
   - `is_active` - Account status

## Configuration

### Environment Variables

```env
# Database Configuration
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=chatdb
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password

# Google AI Configuration
GOOGLE_API_KEY=your_api_key
GOOGLE_MODEL=gemini-pro

# Server Configuration
PORT=8000
HOST=0.0.0.0
DEBUG=True
```

### Database Setup

1. **Create PostgreSQL database**:

   ```sql
   CREATE DATABASE chatdb;
   ```

2. **Run initialization script**:
   ```bash
   python init_db.py
   ```

## AI Integration

The backend is designed to integrate with Google Generative AI through LangChain. The current implementation includes:

- **AIService class** - Placeholder for AI integration
- **Conversation context** - Automatic context management
- **History formatting** - Proper message formatting for AI models

### Implementing AI Integration

To integrate with actual AI services, modify the `AIService` class in `services.py`:

```python
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage

class AIService:
    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model=os.getenv('GOOGLE_MODEL', 'gemini-pro'),
            api_key=os.getenv('GOOGLE_API_KEY')
        )

    def generate_response(self, user_message: str, conversation_history: List[ChatHistory]) -> str:
        # Format conversation history
        messages = self.format_conversation_for_ai(conversation_history)

        # Add current message
        messages.append(HumanMessage(content=user_message))

        # Generate response
        response = self.llm.invoke(messages)
        return response.content
```

## Development

### Project Structure

```
backend/
├── app.py              # FastAPI application
├── models.py           # SQLAlchemy models
├── schemas.py          # Pydantic schemas
├── services.py         # Business logic
├── database.py         # Database configuration
├── init_db.py         # Database initialization
├── start.py           # Server startup script
├── requirements.txt   # Python dependencies
├── .env.example      # Environment template
└── README.md         # This file
```

### Running in Development

```bash
# Install in development mode
pip install -e .

# Start with auto-reload
python start.py

# Or use uvicorn directly
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

### Testing

```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run tests
pytest
```

## Deployment

### Docker Deployment

1. **Build image**:

   ```bash
   docker build -t chatbot-backend .
   ```

2. **Run container**:
   ```bash
   docker run -p 8000:8000 --env-file .env chatbot-backend
   ```

### Production Deployment

1. **Install production dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

2. **Set production environment variables**

3. **Initialize database**:

   ```bash
   python init_db.py
   ```

4. **Start with production server**:
   ```bash
   gunicorn app:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000
   ```

## Monitoring and Logging

- **Health Check**: `/health` endpoint for monitoring
- **Logging**: Configurable log levels
- **Database Connection**: Automatic connection health checks
- **Error Handling**: Comprehensive error responses

## Security Considerations

- **CORS Configuration**: Properly configure allowed origins
- **Input Validation**: All inputs validated with Pydantic
- **SQL Injection Protection**: SQLAlchemy ORM prevents SQL injection
- **Soft Deletes**: Data is marked as deleted, not physically removed

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

MIT License - see LICENSE file for details.

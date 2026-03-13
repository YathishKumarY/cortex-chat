# 🤖 Gemini AI Multimodal Chat Application

A comprehensive AI-powered chat application built with Streamlit and Google's Gemini AI, featuring multimodal conversations, image generation, PDF analysis, web search, and robust user authentication.

![Python](https://img.shields.io/badge/python-v3.9+-blue.svg)
![Streamlit](https://img.shields.io/badge/streamlit-v1.38.0+-red.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

## 🌟 Features

### Core Functionality

- **🗣️ Multimodal Chat**: Engage in conversations using text, images, and PDFs all in one interface
- **🎨 AI Image Generation**: Generate high-quality images from text prompts using Gemini
- **📄 PDF Analysis**: Upload and analyze PDF documents with intelligent Q&A
- **🔍 Real-time Web Search**: Access current information with integrated Google Search
- **🔗 URL Analysis**: Analyze and summarize content from web URLs
- **🔐 Secure Authentication**: User login/logout with encrypted password storage

### Advanced Features

- **💡 Smart Suggestions**: Contextual prompt suggestions based on conversation history
- **📱 Mobile-Responsive**: Optimized UI for desktop and mobile devices
- **💾 Conversation History**: Persistent chat storage with easy management
- **🎯 Context-Aware Responses**: AI maintains conversation context across interactions
- **🔄 Background Processing**: Efficient handling of long-running AI tasks

## 🏗️ Architecture

### Frontend Applications

```
├── main.py                    # Main application with authentication
├── multimodal_chat_old.py    # Primary multimodal chat interface
├── chat.py                   # Basic text chat
├── image_generation.py       # Dedicated image generation tool
├── image_chat.py            # Image-focused chat interface
├── pdf_chat.py              # PDF analysis tool
└── suggestions.py           # Smart prompt suggestions
```

### Backend API (Optional)

```
backend/
├── app.py                    # FastAPI application
├── models.py                # Database models
├── services.py              # Business logic
├── schemas.py               # API schemas
├── database.py              # Database configuration
└── config.py                # Application settings
```

### Authentication System

```
utils/
├── generate-keys.py         # Password hashing utility
└── hashed_pw.pkl           # Encrypted user credentials
```

## 🚀 Quick Start

### Prerequisites

- Python 3.9+
- Google Gemini API key
- (Optional) PostgreSQL for backend storage

### Installation

1. **Clone the repository**

```bash
git clone https://github.com/yourusername/gemini-ai-chat.git
cd gemini-ai-chat
```

2. **Create virtual environment**

```bash
python3 -m venv myenv
source myenv/bin/activate  # On Windows: myenv\Scripts\activate
```

3. **Install dependencies**

```bash
pip install -r requirements.txt
```

4. **Set up environment variables**
   Create a `.streamlit/secrets.toml` file:

```toml
GEMINI_API_KEY = "your_gemini_api_key_here"
```

Or create a `.env` file:

```env
GEMINI_API_KEY=your_gemini_api_key_here
```

5. **Generate authentication keys** (First time only)

```bash
cd utils
python generate-keys.py
```

6. **Run the application**

```bash
streamlit run main.py
```

### Default Login Credentials

- **Username**: `johndoe` / **Password**: `password123`
- **Username**: `janesmith` / **Password**: `mypassword`

## 🔧 Configuration

### User Authentication

Edit `utils/generate-keys.py` to customize user accounts:

```python
names = ["Your Name", "Another User"]
usernames = ["yourusername", "otherusername"]
passwords = ["yourpassword", "otherpassword"]
```

Then regenerate the password hashes:

```bash
cd utils
python generate-keys.py
```

### API Settings

Configure Gemini AI settings in your secrets file:

```toml
# .streamlit/secrets.toml
GEMINI_API_KEY = "your_api_key"

# Optional: Custom model settings
GEMINI_MODEL = "gemini-2.5-pro"
```

## 📖 Usage Guide

### Getting Started

1. **Login**: Use the provided credentials or create new ones
2. **Choose Chat Mode**: Select from multimodal, image generation, or PDF analysis
3. **Upload Files**: Drag and drop images or PDFs for analysis
4. **Enable Features**: Toggle web search and URL analysis as needed
5. **Start Chatting**: Engage with the AI using text, images, or documents

### Multimodal Chat Features

- **Text Conversations**: Standard chat functionality with conversation history
- **Image Upload**: Upload images for analysis, description, or editing
- **PDF Processing**: Upload PDFs for content extraction and Q&A
- **Web Search**: Enable real-time web search for current information
- **URL Analysis**: Paste URLs for content summarization and analysis
- **Smart Suggestions**: Use AI-generated prompts for inspiration

### Advanced Usage

- **Image Generation**: Create custom images with detailed prompts
- **Document Analysis**: Extract key insights from uploaded documents
- **Conversation Management**: Save, load, and organize chat sessions
- **Context Awareness**: Build on previous conversations for deeper insights

## 🔌 Backend Setup (Optional)

For persistent storage and API access:

1. **Navigate to backend directory**

```bash
cd backend
```

2. **Set up PostgreSQL**

```bash
chmod +x setup_postgres.sh
./setup_postgres.sh
```

3. **Configure environment**

```bash
cp .env.example .env
# Edit .env with your database settings
```

4. **Run database migrations**

```bash
alembic upgrade head
```

5. **Start the API server**

```bash
python app.py
```

The API will be available at `http://localhost:8000` with documentation at `/docs`.

## 📦 Dependencies

### Core Requirements

```
streamlit==1.38.0
google-generativeai==0.7.2
google-genai==1.30.0
streamlit-authenticator==0.4.2
python-dotenv==1.0.1
PyPDF2==3.0.1
joblib==1.4.2
```

### Backend Requirements (Optional)

```
fastapi
uvicorn[standard]
sqlalchemy
psycopg2-binary
alembic
```

## 🐳 Docker Support

### Frontend Only

```bash
docker build -t gemini-chat .
docker run -p 8501:8501 -e GEMINI_API_KEY=your_key gemini-chat
```

### Full Stack (with Backend)

```bash
cd backend
docker-compose up -d
```

## 🤝 Contributing

We welcome contributions! Here's how to get started:

1. **Fork the repository**
2. **Create a feature branch**

```bash
git checkout -b feature/amazing-feature
```

3. **Make your changes**
4. **Add tests** (if applicable)
5. **Commit your changes**

```bash
git commit -m 'Add some amazing feature'
```

6. **Push to the branch**

```bash
git push origin feature/amazing-feature
```

7. **Open a Pull Request**

### Development Guidelines

- Follow PEP 8 style guidelines
- Add docstrings to new functions
- Test your changes thoroughly
- Update documentation as needed

## 🧪 Testing

Run the test suite:

```bash
# Frontend tests
python -m pytest tests/

# Backend API tests
cd backend
python -m pytest
```

## 📊 Performance Optimization

### Frontend Performance

- **Caching**: Uses Streamlit's caching for API responses
- **Session Management**: Efficient state management across pages
- **File Processing**: Optimized PDF and image handling
- **Memory Management**: Proper cleanup of large objects

### Backend Performance

- **Database Optimization**: Indexed queries and connection pooling
- **API Rate Limiting**: Built-in rate limiting for API endpoints
- **Async Processing**: Asynchronous handling of AI requests
- **Caching Strategy**: Redis integration for response caching

## 🔒 Security Features

- **Password Encryption**: BCrypt hashing for user passwords
- **Session Management**: Secure cookie-based authentication
- **Input Validation**: Comprehensive input sanitization
- **API Security**: CORS configuration and request validation
- **File Upload Security**: Safe file handling and validation

### Heroku Deployment

```bash
# Create Procfile
echo "web: streamlit run main.py --server.port=$PORT --server.address=0.0.0.0" > Procfile

# Deploy
heroku create your-app-name
heroku config:set GEMINI_API_KEY=your_key
git push heroku main
```

## 🎯 Roadmap

### Upcoming Features

- [ ] **Voice Chat**: Speech-to-text and text-to-speech capabilities
- [ ] **Video Analysis**: Upload and analyze video content
- [ ] **Team Collaboration**: Multi-user chat rooms and sharing
- [ ] **API Integrations**: Connect with more AI services
- [ ] **Custom Models**: Support for fine-tuned Gemini models
- [ ] **Analytics Dashboard**: Usage statistics and insights
- [ ] **Mobile App**: Native iOS and Android applications
- [ ] **Plugin System**: Extensible architecture for custom features

### Technical Improvements

- [ ] **Performance**: Optimize loading times and responsiveness
- [ ] **Scalability**: Kubernetes deployment and auto-scaling
- [ ] **Monitoring**: Comprehensive logging and error tracking
- [ ] **Testing**: Increased test coverage and automated testing
- [ ] **Documentation**: Interactive API documentation and tutorials

## 🐛 Troubleshooting

### Common Issues

**Authentication Problems**

```bash
# Regenerate authentication keys
cd utils
python generate-keys.py
```

**API Key Issues**

- Verify your Gemini API key is correct
- Check rate limits and quotas
- Ensure proper environment variable setup

**File Upload Problems**

- Check file size limits (default: 50MB)
- Verify supported file types (PDF, JPG, PNG, TXT)
- Ensure proper file permissions

**Performance Issues**

- Clear browser cache and cookies
- Check system memory usage
- Verify internet connection stability

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/yourusername/gemini-ai-chat/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/gemini-ai-chat/discussions)
- **Email**: your-email@example.com

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **Google Gemini AI**: For providing the powerful AI capabilities
- **Streamlit**: For the amazing web app framework
- **Contributors**: Thank you to all contributors who help improve this project
- **Community**: Special thanks to the open-source community

---

## 📈 Project Statistics

- **Lines of Code**: ~3,000+
- **Features**: 15+ major features
- **Supported Formats**: PDF, JPG, PNG, TXT
- **AI Models**: Gemini 2.5 Pro/Flash
- **Authentication**: Secure multi-user support

---

**Built with ❤️ using Google Gemini AI and Streamlit**

_Last updated: September 2025_

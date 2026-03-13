# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the Project

### Frontend (Streamlit)
```bash
source myenv/bin/activate
streamlit run main.py          # Auth entry point → redirects to multimodal_chat
streamlit run multimodal_chat.py  # Direct access (bypasses auth)
```
Frontend runs on port 8502 (configured in `.streamlit/config.toml`).

### Backend (FastAPI + PostgreSQL)
```bash
cd backend
podman-compose up -d           # Starts postgres (port 5434) + fastapi (port 8000) + pgadmin (port 5050)
podman-compose down            # Stop all services
```

To run the backend manually:
```bash
cd backend
python init_db.py              # Initialize database tables
python start.py                # Start FastAPI on port 8000
```

### Database Migrations
```bash
cd backend
alembic upgrade head           # Apply all migrations
alembic revision --autogenerate -m "description"  # Create new migration
```

### Tests
```bash
python -m pytest tests/        # Frontend tests
cd backend && python -m pytest # Backend tests
```

### Health Check
```bash
curl http://localhost:8000/health
```
API docs available at `http://localhost:8000/docs`.

## Architecture

**Two-tier app: Streamlit frontend + optional FastAPI/PostgreSQL backend.**

- `main.py` — Authentication entry point (login/register with JWT stored in cookies)
- `multimodal_chat.py` — The main app (~2600 lines, monolithic). Handles all chat features: text, image upload, PDF analysis, web search, URL analysis, image generation. Falls back to local joblib storage in `data/` when backend is unavailable.
- `api_client.py` — `GeminiAPIClient` class connecting frontend to backend. Routes have no `/api/` prefix (e.g., `/auth/login`, `/chat`, `/conversations/{id}/history`).
- `backend/app.py` — FastAPI server with public endpoints (`/health`, `/auth/register`, `/auth/login`) and JWT-protected endpoints (`/chat`, `/conversations/*`, `/users/*`).
- `backend/services.py` — Business logic layer: `ChatService`, `ConversationService`, `UserService`, `AIService`.
- `backend/models.py` — SQLAlchemy ORM: `User`, `Conversation`, `ChatHistory` tables. Uses soft deletes (`is_deleted` flag).
- `backend/auth.py` — JWT creation/validation with bcrypt password hashing. `get_current_user` FastAPI dependency for protected routes.

### Auth Flow
1. User registers/logs in via `main.py`
2. Backend returns JWT token
3. Token stored in browser cookies via `extra-streamlit-components` CookieManager (24hr max-age)
4. All subsequent API calls use `Authorization: Bearer {token}`

### Data Storage Fallback
When backend is unavailable, `multimodal_chat.py` persists conversations locally using joblib serialization to `data/` directory.

## Key Constraints

- **Free tier only**: Use `gemini-2.5-flash` for chat. Models `gemini-2.0-flash`, `gemini-2.5-pro`, `gemini-1.5-flash` are blocked (limit:0). Image generation (`gemini-2.0-flash-preview-image-generation`) has no free alternative.
- **Podman, not Docker**: Use `podman-compose` for container management.
- **PostgreSQL port 5434**: Mapped to avoid conflict with local postgres on 5432.
- **Virtual env is `myenv/`**, not `venv/`.

## Environment Variables

**Frontend**: `GEMINI_API_KEY` — loaded from `.streamlit/secrets.toml` first, then `.env`.

**Backend** (see `backend/.env.example`): `POSTGRES_HOST`, `POSTGRES_PORT` (5434), `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `GOOGLE_API_KEY`, `SECRET_KEY`, `ACCESS_TOKEN_EXPIRE_MINUTES` (default 30), `CORS_ORIGINS`, `PORT`, `HOST`, `DEBUG`, `LOG_LEVEL`.

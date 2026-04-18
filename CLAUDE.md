# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Project Management MVP - a Kanban board web app with AI-powered card management. Single-user MVP running in Docker with Next.js frontend, FastAPI backend, SQLite database, and OpenRouter AI integration.

## Development Commands

### Local Development (Container)

Start the application:
```bash
# macOS/Linux
./scripts/start-mac.sh  # or ./scripts/start-linux.sh
# Windows
./scripts/start-windows.ps1
```

Stop the application:
```bash
# macOS/Linux
./scripts/stop-mac.sh  # or ./scripts/stop-linux.sh
# Windows
./scripts/stop-windows.ps1
```

The app runs on port 80. Access at http://localhost

### Frontend Development

```bash
cd frontend
npm install
npm run dev          # Development server
npm run build        # Production build
npm run lint         # ESLint
npm run test:unit    # Vitest unit tests
npm run test:e2e     # Playwright e2e tests
npm run test:all     # Run all tests
```

Minimum test coverage: 80% (statements, branches, functions, lines)

### Backend Development

```bash
cd backend
# Dependencies are managed with uv (installed in Docker)
# Run backend tests
uv run pytest
uv run pytest --cov  # With coverage report
```

Backend runs on uvicorn serving FastAPI app at `backend.app.main:app`

## Architecture

### Full Stack Flow

1. **Docker Build**: Frontend builds static export → copied into backend/static → served by FastAPI
2. **Routing**: FastAPI serves static files at `/`, API routes at `/api/*`, health check at `/up`
3. **Data Flow**: Frontend → FastAPI API → SQLite → OpenRouter (for AI chat)
4. **State Management**: Backend is source of truth; frontend fetches/updates via API

### Backend Structure

- `backend/app/main.py` - FastAPI app, all API routes, request/response models, operation handlers
- `backend/app/db.py` - SQLite schema, connection management, seed data, user/board initialization
- `backend/app/auth.py` - JWT authentication with HTTPBearer, token creation/validation
- `backend/app/config.py` - Pydantic Settings for centralized configuration
- `backend/app/openrouter.py` - OpenRouter API client for AI chat completions
- `backend/app/errors.py` - Standardized error response format
- `backend/app/logging_config.py` - Structured logging with request/response middleware

**Key Backend Patterns:**
- Database initialized on startup via FastAPI lifespan context manager
- Single hardcoded user (configurable via `PM_USERNAME`/`PM_PASSWORD` env vars)
- One board per user enforced by unique index on `boards.user_id`
- All IDs are UUID hex strings stored as TEXT
- Position-based ordering for columns and cards (integer `position` field)
- Foreign keys with CASCADE delete enabled
- `ensure_user_and_board()` creates user and board with seed data if missing
- JWT authentication on all protected routes via `Depends(get_current_user)`
- Password hashing with bcrypt before storage
- Transaction management for multi-step database operations
- CORS and security headers configured in middleware

### Frontend Structure

- `src/app/page.tsx` - Main Kanban board page
- `src/components/KanbanBoard.tsx` - Board state management, drag/drop with @dnd-kit
- `src/components/KanbanColumn.tsx` - Column rendering, editable titles
- `src/components/KanbanCard.tsx` - Card rendering with modal for edit/delete
- `src/components/NewCardForm.tsx` - Card creation form
- `src/lib/kanban.ts` - Type definitions and card movement logic

**Frontend Technologies:**
- Next.js 16 App Router with static export (`output: 'export'`)
- React 19 with TypeScript
- Tailwind CSS (utility classes)
- @dnd-kit for drag and drop
- Vitest for unit tests, Playwright for e2e tests

### Database Schema

SQLite database at `backend/data/pm.db` (configurable via `PM_DB_PATH` env var)

Tables: `users`, `boards`, `columns`, `cards`
- `boards.user_id` has unique index (one board per user)
- `columns` and `cards` have position-based ordering
- Foreign keys cascade on delete
- All timestamps in ISO 8601 UTC format

Reordering strategy: Update positions within parent scope, using temporary negative positions to avoid unique constraint conflicts during reorder operations.

### AI Integration

OpenRouter API (`openai/gpt-oss-120b` model) via `/api/chat` endpoint:
1. Frontend sends user message + conversation history
2. Backend builds context with full board JSON + conversation + new message
3. AI returns structured JSON: `{reply: string, operations: array}`
4. Backend parses and validates operations
5. Backend applies operations (create/update/move/delete cards/columns)
6. Frontend receives reply + operations, refreshes board state

**Operation Types:**
- Column ops: `create_column`, `rename_column`, `move_column`, `delete_column`
- Card ops: `create_card`, `update_card`, `move_card`, `delete_card`
- Board ops: `update_board_title`

**Key AI Implementation Details:**
- `parse_model_output()` handles JSON extraction from markdown code fences
- `normalize_operation_keys()` cleans up key formatting variations
- `normalize_move_card_target()` supports multiple ways AI might specify target column (by ID, by title, by various key names)
- All operations are discriminated unions validated with Pydantic

## Environment Variables

Create `.env` file (see `.env.example`):
```
OPENROUTER_API_KEY=       # Required for AI chat
JWT_SECRET_KEY=           # Required for authentication (generate with: openssl rand -hex 32)
PM_USERNAME=jared         # Login username (default: jared)
PM_PASSWORD=              # Login password (default: password)
PM_DB_PATH=               # Optional: custom database path
```

**Required Variables:**
- `OPENROUTER_API_KEY` - OpenRouter API key for AI chat functionality
- `JWT_SECRET_KEY` - Secret key for signing JWT tokens (must be strong random value)
- `PM_PASSWORD` - User password (hashed with bcrypt before storage)

**Optional Variables:**
- `PM_USERNAME` - Defaults to "jared"
- `PM_DB_PATH` - Defaults to `backend/data/pm.db`
- `JWT_ALGORITHM` - Defaults to "HS256"
- `JWT_EXPIRATION_MINUTES` - Defaults to 1440 (24 hours)

## API Endpoints

**All endpoints except `/api/login`, `/api/health`, and `/up` require JWT authentication via `Authorization: Bearer <token>` header.**

Authentication:
- `POST /api/login` - Login with username/password, returns JWT token

Board:
- `GET /api/board` - Get board with all columns and cards (requires auth)
- `PATCH /api/board` - Update board title (requires auth)

Columns:
- `POST /api/columns` - Create column (requires auth)
- `PATCH /api/columns/{id}` - Update column title/position (requires auth)
- `DELETE /api/columns/{id}` - Delete column (cascades to cards) (requires auth)

Cards:
- `POST /api/cards` - Create card (requires auth)
- `PATCH /api/cards/{id}` - Update card title/details/position/column (requires auth)
- `DELETE /api/cards/{id}` - Delete card (requires auth)

AI:
- `POST /api/chat` - Send message, get AI reply + board operations (requires auth)

Health:
- `GET /api/health` - JSON status check (no auth required)
- `GET /up` - Plain text "OK" (for container health checks) (no auth required)

## Security

**Authentication:**
- JWT tokens with HTTPBearer scheme
- Tokens expire after 24 hours (configurable)
- Password hashing with bcrypt (12 rounds)
- Passwords stored as bcrypt hashes in database
- Token validation via `get_current_user()` dependency

**Security Headers:**
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Strict-Transport-Security: max-age=31536000; includeSubDomains`
- `X-XSS-Protection: 1; mode=block`
- `Referrer-Policy: strict-origin-when-cross-origin`

**CORS:**
- Configured for local development (http://localhost:3000)
- Allows credentials, all methods, common headers

**Input Validation:**
- All request payloads validated with Pydantic models
- Chat input sanitized (stripped and length-limited)

**Docker Security:**
- Runs as non-root user (appuser, uid 1001)
- Minimal attack surface

## Testing Patterns

**Backend Tests:**
- Use `TestClient` from FastAPI
- Create fresh database for each test with `tmp_path` fixture
- Set all required environment variables in test fixtures:
  ```python
  monkeypatch.setenv("PM_USERNAME", "jared")
  monkeypatch.setenv("PM_PASSWORD", "test-password")
  monkeypatch.setenv("JWT_SECRET_KEY", "test-jwt-secret")
  reload_settings()  # Reload config after setting env vars
  ```
- Create auth headers with `create_access_token()`:
  ```python
  token = create_access_token({"sub": "jared"})
  headers = {"Authorization": f"Bearer {token}"}
  ```
- Pass auth headers to all protected endpoints
- Call `ensure_user_and_board()` indirectly via first API request

**Frontend E2E Tests:**
- Playwright tests against running Docker container
- Login helper function for authentication
- Use `data-testid` attributes for stable selectors
- Use `.last()` when multiple elements may exist with same content
- Playwright config uses `reuseExistingServer: true` to avoid rebuilding

## Color Scheme

Defined in AGENTS.md, used throughout frontend:
- Accent Yellow: `#ecad0a` - highlights, accent lines
- Blue Primary: `#209dd7` - links, key sections
- Purple Secondary: `#753991` - buttons, actions
- Dark Navy: `#032147` - headings
- Gray Text: `#888888` - supporting text

## Coding Standards

1. Use latest library versions and idiomatic patterns
2. Simplicity over complexity - no over-engineering or defensive programming
3. No emojis in code or documentation
4. Investigate root causes before attempting fixes - no guessing
5. Minimal documentation - code should be clear
6. 80% minimum test coverage for new code
7. Robust integration testing for API and UI flows

## Publishing

GitHub Container Registry (GHCR):
```bash
./scripts/publish-ghcr.sh
```

Builds and pushes Docker image to GitHub Container Registry. Requires GitHub authentication and repository permissions.

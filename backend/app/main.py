"""FastAPI application for PM MVP - Kanban board with AI integration."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
import uuid

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
# Rate limiting removed - should be handled at infrastructure level
# (reverse proxy, API gateway, or cloud provider)
# from slowapi import Limiter, _rate_limit_exceeded_handler
# from slowapi.errors import RateLimitExceeded
# from slowapi.util import get_remote_address

from .auth import create_access_token, get_current_user
from .config import validate_settings
from .db import ensure_user_and_board, get_connection, init_db, utc_now, verify_password
from .errors import APIError, api_error_handler, http_exception_handler
from .logging_config import log_requests, logger, setup_logging
from .models import (
    BoardResponse,
    BoardUpdate,
    CardCreate,
    CardResponse,
    CardUpdate,
    ChatRequest,
    ChatResponse,
    ColumnCreate,
    ColumnResponse,
    ColumnUpdate,
    LoginRequest,
    LoginResponse,
)
from .openrouter import fetch_chat_completion
from .services import (
    apply_operations,
    build_board,
    build_chat_messages,
    fetch_card_ids,
    fetch_column_ids,
    normalize_details,
    park_card_position,
    parse_model_output,
    reorder_cards,
    reorder_columns,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    setup_logging()
    logger.info("Starting application...")
    validate_settings()
    logger.info("Configuration validated")
    init_db()
    logger.info("Database initialized")
    yield
    logger.info("Shutting down application...")


# Rate limiting should be handled at infrastructure level
# limiter = Limiter(key_func=get_remote_address)
app = FastAPI(lifespan=lifespan)
# app.state.limiter = limiter
# app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_exception_handler(APIError, api_error_handler)
app.add_exception_handler(HTTPException, http_exception_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost", "http://localhost:80"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


app.middleware("http")(log_requests)

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
INDEX_FILE = STATIC_DIR / "index.html"


# Health and Authentication Routes


@app.get("/api/health")
def read_health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/login", response_model=LoginResponse)
def login(payload: LoginRequest) -> LoginResponse:
    connection = get_connection()
    try:
        ensure_user_and_board(connection)

        user_row = connection.execute(
            "SELECT id, password_hash FROM users WHERE username = ?",
            (payload.username,),
        ).fetchone()

        if not user_row:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        if not verify_password(payload.password, user_row["password_hash"]):
            raise HTTPException(status_code=401, detail="Invalid credentials")

        token = create_access_token({"sub": payload.username})
        return LoginResponse(status="ok", token=token)
    finally:
        connection.close()


@app.get("/up", response_class=PlainTextResponse)
def read_up() -> str:
    return "OK"


# Board Routes


@app.get("/api/board", response_model=BoardResponse)
def read_board(username: str = Depends(get_current_user)) -> BoardResponse:
    connection = get_connection()
    try:
        board_id = ensure_user_and_board(connection)
        return build_board(connection, board_id)
    finally:
        connection.close()


@app.patch("/api/board", response_model=BoardResponse)
def update_board(
    payload: BoardUpdate, username: str = Depends(get_current_user)
) -> BoardResponse:
    connection = get_connection()
    try:
        board_id = ensure_user_and_board(connection)
        now = utc_now()
        connection.execute(
            "UPDATE boards SET title = ?, updated_at = ? WHERE id = ?",
            (payload.title, now, board_id),
        )
        connection.commit()
        return build_board(connection, board_id)
    finally:
        connection.close()


# Chat Route


@app.post("/api/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest, username: str = Depends(get_current_user)
) -> ChatResponse:
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message is required")
    if len(message) > 1000:
        raise HTTPException(status_code=400, detail="Message too long (max 1000 characters)")
    if len(payload.conversation or []) > 50:
        raise HTTPException(
            status_code=400, detail="Conversation too long (max 50 messages)"
        )
    connection = get_connection()
    try:
        board_id = ensure_user_and_board(connection)
        board = build_board(connection, board_id)
        messages = build_chat_messages(payload, board)
        raw_reply = await fetch_chat_completion(messages)
        model_output = parse_model_output(raw_reply, board)
        apply_operations(connection, board_id, model_output.operations)
        return ChatResponse(
            reply=model_output.reply,
            operations=model_output.operations,
        )
    finally:
        connection.close()


# Column Routes


@app.post("/api/columns", response_model=ColumnResponse)
def create_column(
    payload: ColumnCreate, username: str = Depends(get_current_user)
) -> ColumnResponse:
    connection = get_connection()
    try:
        board_id = ensure_user_and_board(connection)
        now = utc_now()
        column_id = uuid.uuid4().hex
        existing_ids = fetch_column_ids(connection, board_id)
        connection.execute(
            """
            INSERT INTO columns (id, board_id, title, position, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (column_id, board_id, payload.title, len(existing_ids), now, now),
        )
        insert_at = payload.position
        next_ids = existing_ids + [column_id]
        if insert_at is not None:
            insert_at = max(0, min(insert_at, len(existing_ids)))
            next_ids.pop()
            next_ids.insert(insert_at, column_id)
        reorder_columns(connection, board_id, next_ids)
        return ColumnResponse(
            id=column_id,
            title=payload.title,
            position=next_ids.index(column_id),
            cardIds=[],
        )
    finally:
        connection.close()


@app.patch("/api/columns/{column_id}", response_model=ColumnResponse)
def update_column(
    column_id: str, payload: ColumnUpdate, username: str = Depends(get_current_user)
) -> ColumnResponse:
    connection = get_connection()
    try:
        row = connection.execute(
            "SELECT id, board_id FROM columns WHERE id = ?",
            (column_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Column not found")

        now = utc_now()
        if payload.title is not None:
            connection.execute(
                "UPDATE columns SET title = ?, updated_at = ? WHERE id = ?",
                (payload.title, now, column_id),
            )

        if payload.position is not None:
            ordered_ids = fetch_column_ids(connection, row["board_id"])
            if column_id in ordered_ids:
                ordered_ids.remove(column_id)
            insert_at = max(0, min(payload.position, len(ordered_ids)))
            ordered_ids.insert(insert_at, column_id)
            reorder_columns(connection, row["board_id"], ordered_ids)

        connection.commit()
        column_row = connection.execute(
            "SELECT id, title, position FROM columns WHERE id = ?",
            (column_id,),
        ).fetchone()
        card_ids = fetch_card_ids(connection, column_id)
        return ColumnResponse(
            id=column_row["id"],
            title=column_row["title"],
            position=column_row["position"],
            cardIds=card_ids,
        )
    finally:
        connection.close()


@app.delete("/api/columns/{column_id}")
def delete_column(
    column_id: str, username: str = Depends(get_current_user)
) -> dict[str, str]:
    connection = get_connection()
    try:
        row = connection.execute(
            "SELECT id, board_id FROM columns WHERE id = ?",
            (column_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Column not found")

        connection.execute("DELETE FROM columns WHERE id = ?", (column_id,))
        remaining_ids = fetch_column_ids(connection, row["board_id"])
        reorder_columns(connection, row["board_id"], remaining_ids)
        return {"status": "ok"}
    finally:
        connection.close()


# Card Routes


@app.post("/api/cards", response_model=CardResponse)
def create_card(
    payload: CardCreate, username: str = Depends(get_current_user)
) -> CardResponse:
    connection = get_connection()
    try:
        column_row = connection.execute(
            "SELECT id FROM columns WHERE id = ?",
            (payload.column_id,),
        ).fetchone()
        if not column_row:
            raise HTTPException(status_code=404, detail="Column not found")

        now = utc_now()
        card_id = uuid.uuid4().hex
        existing_ids = fetch_card_ids(connection, payload.column_id)
        connection.execute(
            """
            INSERT INTO cards
              (id, column_id, title, details, position, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                card_id,
                payload.column_id,
                payload.title,
                normalize_details(payload.details),
                len(existing_ids),
                now,
                now,
            ),
        )
        insert_at = payload.position
        next_ids = existing_ids + [card_id]
        if insert_at is not None:
            insert_at = max(0, min(insert_at, len(existing_ids)))
            next_ids.pop()
            next_ids.insert(insert_at, card_id)
        reorder_cards(connection, payload.column_id, next_ids)
        return CardResponse(
            id=card_id,
            title=payload.title,
            details=normalize_details(payload.details),
            position=next_ids.index(card_id),
            columnId=payload.column_id,
        )
    finally:
        connection.close()


@app.patch("/api/cards/{card_id}", response_model=CardResponse)
def update_card(
    card_id: str, payload: CardUpdate, username: str = Depends(get_current_user)
) -> CardResponse:
    connection = get_connection()
    try:
        card_row = connection.execute(
            "SELECT id, column_id FROM cards WHERE id = ?",
            (card_id,),
        ).fetchone()
        if not card_row:
            raise HTTPException(status_code=404, detail="Card not found")

        now = utc_now()
        if payload.title is not None:
            connection.execute(
                "UPDATE cards SET title = ?, updated_at = ? WHERE id = ?",
                (payload.title, now, card_id),
            )
        if payload.details is not None:
            connection.execute(
                "UPDATE cards SET details = ?, updated_at = ? WHERE id = ?",
                (normalize_details(payload.details), now, card_id),
            )

        current_column_id = card_row["column_id"]
        target_column_id = payload.column_id or current_column_id
        if target_column_id != current_column_id:
            target_exists = connection.execute(
                "SELECT id FROM columns WHERE id = ?",
                (target_column_id,),
            ).fetchone()
            if not target_exists:
                raise HTTPException(status_code=404, detail="Target column not found")

        if payload.position is not None or target_column_id != current_column_id:
            park_card_position(connection, card_id)
            current_ids = fetch_card_ids(connection, current_column_id)
            if card_id in current_ids:
                current_ids.remove(card_id)
            reorder_cards(connection, current_column_id, current_ids)

            target_ids = fetch_card_ids(connection, target_column_id)
            insert_at = payload.position
            if insert_at is None:
                insert_at = len(target_ids)
            insert_at = max(0, min(insert_at, len(target_ids)))
            target_ids.insert(insert_at, card_id)
            connection.execute(
                """
                UPDATE cards
                SET column_id = ?, position = ?, updated_at = ?
                WHERE id = ?
                """,
                (target_column_id, -1, now, card_id),
            )
            reorder_cards(connection, target_column_id, target_ids)

        connection.commit()
        updated_row = connection.execute(
            """
            SELECT id, title, details, position, column_id
            FROM cards WHERE id = ?
            """,
            (card_id,),
        ).fetchone()
        return CardResponse(
            id=updated_row["id"],
            title=updated_row["title"],
            details=updated_row["details"],
            position=updated_row["position"],
            columnId=updated_row["column_id"],
        )
    finally:
        connection.close()


@app.delete("/api/cards/{card_id}")
def delete_card(card_id: str, username: str = Depends(get_current_user)) -> dict[str, str]:
    connection = get_connection()
    try:
        row = connection.execute(
            "SELECT id, column_id FROM cards WHERE id = ?",
            (card_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Card not found")

        connection.execute("DELETE FROM cards WHERE id = ?", (card_id,))
        remaining_ids = fetch_card_ids(connection, row["column_id"])
        reorder_cards(connection, row["column_id"], remaining_ids)
        return {"status": "ok"}
    finally:
        connection.close()


# Static File Serving


@app.get("/", response_class=HTMLResponse)
def read_root() -> HTMLResponse:
    if INDEX_FILE.exists():
        return FileResponse(INDEX_FILE)

    return HTMLResponse(
        """
        <!doctype html>
        <html lang=\"en\">
          <head>
          <meta charset=\"utf-8\" />
          <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
          <title>PM MVP</title>
          </head>
          <body>
          <main style=\"font-family: Arial, sans-serif; padding: 40px;\">
            <h1>PM MVP</h1>
            <p>Static frontend not built yet. Run the frontend export step.</p>
            <p>Try <code>/api/health</code> for a JSON response.</p>
          </main>
          </body>
        </html>
        """
    )


if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")

from __future__ import annotations

import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DEFAULT_USERNAME = "user"
DEFAULT_USER_ID = "user-1"
DEFAULT_BOARD_TITLE = "Kanban Studio"

DEFAULT_COLUMNS = [
    {
        "title": "Backlog",
        "cards": [
            (
                "Align roadmap themes",
                "Draft quarterly themes with impact statements and metrics.",
            ),
            (
                "Gather customer signals",
                "Review support tags, sales notes, and churn feedback.",
            ),
        ],
    },
    {
        "title": "Discovery",
        "cards": [
            (
                "Prototype analytics view",
                "Sketch initial dashboard layout and key drill-downs.",
            ),
        ],
    },
    {
        "title": "In Progress",
        "cards": [
            (
                "Refine status language",
                "Standardize column labels and tone across the board.",
            ),
            (
                "Design card layout",
                "Add hierarchy and spacing for scanning dense lists.",
            ),
        ],
    },
    {
        "title": "Review",
        "cards": [
            (
                "QA micro-interactions",
                "Verify hover, focus, and loading states.",
            ),
        ],
    },
    {
        "title": "Done",
        "cards": [
            (
                "Ship marketing page",
                "Final copy approved and asset pack delivered.",
            ),
            (
                "Close onboarding sprint",
                "Document release notes and share internally.",
            ),
        ],
    },
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_db_path() -> Path:
    env_path = os.environ.get("PM_DB_PATH")
    if env_path:
        return Path(env_path)
    return BASE_DIR / "data" / "pm.db"


def get_connection() -> sqlite3.Connection:
    db_path = get_db_path()
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db() -> None:
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS boards (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE UNIQUE INDEX IF NOT EXISTS idx_boards_user_id
                ON boards(user_id);

            CREATE TABLE IF NOT EXISTS columns (
                id TEXT PRIMARY KEY,
                board_id TEXT NOT NULL REFERENCES boards(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                position INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE UNIQUE INDEX IF NOT EXISTS idx_columns_board_position
                ON columns(board_id, position);

            CREATE TABLE IF NOT EXISTS cards (
                id TEXT PRIMARY KEY,
                column_id TEXT NOT NULL REFERENCES columns(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                details TEXT NOT NULL,
                position INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE UNIQUE INDEX IF NOT EXISTS idx_cards_column_position
                ON cards(column_id, position);
            """
        )


def ensure_user_and_board(connection: sqlite3.Connection) -> str:
    user_row = connection.execute(
        "SELECT id FROM users WHERE username = ?",
        (DEFAULT_USERNAME,),
    ).fetchone()
    now = utc_now()

    if not user_row:
        connection.execute(
            """
            INSERT INTO users (id, username, password_hash, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (DEFAULT_USER_ID, DEFAULT_USERNAME, "demo", now, now),
        )
        user_id = DEFAULT_USER_ID
    else:
        user_id = user_row["id"]

    board_row = connection.execute(
        "SELECT id FROM boards WHERE user_id = ?",
        (user_id,),
    ).fetchone()

    if not board_row:
        board_id = uuid.uuid4().hex
        connection.execute(
            """
            INSERT INTO boards (id, user_id, title, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (board_id, user_id, DEFAULT_BOARD_TITLE, now, now),
        )
        seed_board(connection, board_id)
        return board_id

    board_id = board_row["id"]
    columns_count = connection.execute(
        "SELECT COUNT(*) as count FROM columns WHERE board_id = ?",
        (board_id,),
    ).fetchone()
    if columns_count and columns_count["count"] == 0:
        seed_board(connection, board_id)

    return board_id


def seed_board(connection: sqlite3.Connection, board_id: str) -> None:
    now = utc_now()
    for column_index, column in enumerate(DEFAULT_COLUMNS):
        column_id = uuid.uuid4().hex
        connection.execute(
            """
            INSERT INTO columns (id, board_id, title, position, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (column_id, board_id, column["title"], column_index, now, now),
        )
        for card_index, (title, details) in enumerate(column["cards"]):
            card_id = uuid.uuid4().hex
            connection.execute(
                """
                INSERT INTO cards
                    (id, column_id, title, details, position, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (card_id, column_id, title, details, card_index, now, now),
            )
    connection.commit()

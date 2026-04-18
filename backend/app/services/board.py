"""Board building and utility functions."""

from __future__ import annotations

import sqlite3

from fastapi import HTTPException

from ..models import BoardResponse, CardResponse, ColumnResponse


def normalize_details(details: str | None) -> str:
    """Normalize card details, returning default text if empty."""
    if details and details.strip():
        return details.strip()
    return "No details yet."


def build_board(connection: sqlite3.Connection, board_id: str) -> BoardResponse:
    """Build complete board state from database."""
    board_row = connection.execute(
        "SELECT id, title FROM boards WHERE id = ?",
        (board_id,),
    ).fetchone()
    if not board_row:
        raise HTTPException(status_code=404, detail="Board not found")

    column_rows = connection.execute(
        """
        SELECT id, title, position
        FROM columns
        WHERE board_id = ?
        ORDER BY position
        """,
        (board_id,),
    ).fetchall()

    card_rows = connection.execute(
        """
        SELECT cards.id, cards.title, cards.details, cards.position, cards.column_id
        FROM cards
        JOIN columns ON columns.id = cards.column_id
        WHERE columns.board_id = ?
        ORDER BY columns.position, cards.position
        """,
        (board_id,),
    ).fetchall()

    card_ids_by_column: dict[str, list[str]] = {row["id"]: [] for row in column_rows}
    cards: dict[str, CardResponse] = {}
    for row in card_rows:
        card_id = row["id"]
        cards[card_id] = CardResponse(
            id=card_id,
            title=row["title"],
            details=row["details"],
            position=row["position"],
            columnId=row["column_id"],
        )
        card_ids_by_column.setdefault(row["column_id"], []).append(card_id)

    columns = [
        ColumnResponse(
            id=row["id"],
            title=row["title"],
            position=row["position"],
            cardIds=card_ids_by_column.get(row["id"], []),
        )
        for row in column_rows
    ]

    return BoardResponse(
        id=board_row["id"],
        title=board_row["title"],
        columns=columns,
        cards=cards,
    )

"""Column and card reordering logic."""

from __future__ import annotations

import sqlite3

from ..db import utc_now


def fetch_column_ids(connection: sqlite3.Connection, board_id: str) -> list[str]:
    """Fetch all column IDs for a board in position order."""
    rows = connection.execute(
        "SELECT id FROM columns WHERE board_id = ? ORDER BY position",
        (board_id,),
    ).fetchall()
    return [row["id"] for row in rows]


def fetch_card_ids(connection: sqlite3.Connection, column_id: str) -> list[str]:
    """Fetch all card IDs for a column in position order."""
    rows = connection.execute(
        "SELECT id FROM cards WHERE column_id = ? ORDER BY position",
        (column_id,),
    ).fetchall()
    return [row["id"] for row in rows]


def reorder_columns(connection: sqlite3.Connection, board_id: str, ordered_ids: list[str]) -> None:
    """Reorder columns by assigning new positions based on ordered_ids list.

    Uses two-pass approach with negative positions to avoid unique constraint conflicts.
    """
    now = utc_now()
    # First pass: set negative positions
    for index, column_id in enumerate(ordered_ids):
        connection.execute(
            "UPDATE columns SET position = ?, updated_at = ? WHERE id = ?",
            (-(index + 1), now, column_id),
        )
    # Second pass: set final positions
    for index, column_id in enumerate(ordered_ids):
        connection.execute(
            "UPDATE columns SET position = ?, updated_at = ? WHERE id = ?",
            (index, now, column_id),
        )
    connection.commit()


def park_card_position(connection: sqlite3.Connection, card_id: str) -> None:
    """Move card to a temporary position to avoid conflicts during reordering."""
    now = utc_now()
    connection.execute(
        "UPDATE cards SET position = ?, updated_at = ? WHERE id = ?",
        (-999999, now, card_id),
    )


def reorder_cards(connection: sqlite3.Connection, column_id: str, ordered_ids: list[str]) -> None:
    """Reorder cards by assigning new positions based on ordered_ids list.

    Uses two-pass approach with temporary negative positions to avoid unique constraint conflicts.
    """
    now = utc_now()
    # Find minimum position to avoid conflicts
    min_row = connection.execute(
        "SELECT MIN(position) as min_pos FROM cards WHERE column_id = ?",
        (column_id,),
    ).fetchone()
    min_pos = min_row["min_pos"] if min_row and min_row["min_pos"] is not None else 0
    temp_start = min_pos - len(ordered_ids) - 1

    # First pass: set temporary positions
    for index, card_id in enumerate(ordered_ids):
        temp_pos = temp_start + index
        connection.execute(
            "UPDATE cards SET position = ?, updated_at = ? WHERE id = ?",
            (temp_pos, now, card_id),
        )

    # Second pass: set final positions
    for index, card_id in enumerate(ordered_ids):
        connection.execute(
            "UPDATE cards SET position = ?, updated_at = ? WHERE id = ?",
            (index, now, card_id),
        )

    connection.commit()

"""AI chat operation handlers."""

from __future__ import annotations

import sqlite3
import uuid

from fastapi import HTTPException

from ..db import utc_now
from ..models import (
    ChatOperation,
    CreateCardOp,
    CreateColumnOp,
    DeleteCardOp,
    DeleteColumnOp,
    MoveCardOp,
    MoveColumnOp,
    RenameColumnOp,
    UpdateBoardTitleOp,
    UpdateCardOp,
)
from .board import normalize_details
from .reordering import (
    fetch_card_ids,
    fetch_column_ids,
    park_card_position,
    reorder_cards,
    reorder_columns,
)


def apply_operations(
    connection: sqlite3.Connection, board_id: str, operations: list[ChatOperation]
) -> None:
    """Apply a list of chat operations to the board.

    All operations are executed within a single transaction.
    If any operation fails, the entire batch is rolled back.
    """
    if not operations:
        return

    try:
        for operation in operations:
            if isinstance(operation, CreateColumnOp):
                column_id = uuid.uuid4().hex
                existing_ids = fetch_column_ids(connection, board_id)
                now = utc_now()
                connection.execute(
                    """
                    INSERT INTO columns (id, board_id, title, position, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (column_id, board_id, operation.title, len(existing_ids), now, now),
                )
                insert_at = operation.position
                next_ids = existing_ids + [column_id]
                if insert_at is not None:
                    insert_at = max(0, min(insert_at, len(existing_ids)))
                    next_ids.pop()
                    next_ids.insert(insert_at, column_id)
                reorder_columns(connection, board_id, next_ids)
                continue

            if isinstance(operation, RenameColumnOp):
                now = utc_now()
                result = connection.execute(
                    "UPDATE columns SET title = ?, updated_at = ? WHERE id = ?",
                    (operation.title, now, operation.columnId),
                )
                if result.rowcount == 0:
                    raise HTTPException(status_code=404, detail="Column not found")
                connection.commit()
                continue

            if isinstance(operation, MoveColumnOp):
                ordered_ids = fetch_column_ids(connection, board_id)
                if operation.columnId not in ordered_ids:
                    raise HTTPException(status_code=404, detail="Column not found")
                ordered_ids.remove(operation.columnId)
                insert_at = max(0, min(operation.position, len(ordered_ids)))
                ordered_ids.insert(insert_at, operation.columnId)
                reorder_columns(connection, board_id, ordered_ids)
                continue

            if isinstance(operation, DeleteColumnOp):
                row = connection.execute(
                    "SELECT id FROM columns WHERE id = ?",
                    (operation.columnId,),
                ).fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail="Column not found")
                connection.execute("DELETE FROM columns WHERE id = ?", (operation.columnId,))
                remaining_ids = fetch_column_ids(connection, board_id)
                reorder_columns(connection, board_id, remaining_ids)
                continue

            if isinstance(operation, CreateCardOp):
                column_row = connection.execute(
                    "SELECT id FROM columns WHERE id = ?",
                    (operation.columnId,),
                ).fetchone()
                if not column_row:
                    raise HTTPException(status_code=404, detail="Column not found")

                now = utc_now()
                card_id = uuid.uuid4().hex
                existing_ids = fetch_card_ids(connection, operation.columnId)
                connection.execute(
                    """
                    INSERT INTO cards
                      (id, column_id, title, details, position, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        card_id,
                        operation.columnId,
                        operation.title,
                        normalize_details(operation.details),
                        len(existing_ids),
                        now,
                        now,
                    ),
                )
                insert_at = operation.position
                next_ids = existing_ids + [card_id]
                if insert_at is not None:
                    insert_at = max(0, min(insert_at, len(existing_ids)))
                    next_ids.pop()
                    next_ids.insert(insert_at, card_id)
                reorder_cards(connection, operation.columnId, next_ids)
                continue

            if isinstance(operation, UpdateCardOp):
                card_row = connection.execute(
                    "SELECT id FROM cards WHERE id = ?",
                    (operation.cardId,),
                ).fetchone()
                if not card_row:
                    raise HTTPException(status_code=404, detail="Card not found")

                now = utc_now()
                if operation.title is not None:
                    connection.execute(
                        "UPDATE cards SET title = ?, updated_at = ? WHERE id = ?",
                        (operation.title, now, operation.cardId),
                    )
                if operation.details is not None:
                    connection.execute(
                        "UPDATE cards SET details = ?, updated_at = ? WHERE id = ?",
                        (normalize_details(operation.details), now, operation.cardId),
                    )
                connection.commit()
                continue

            if isinstance(operation, MoveCardOp):
                card_row = connection.execute(
                    "SELECT id, column_id FROM cards WHERE id = ?",
                    (operation.cardId,),
                ).fetchone()
                if not card_row:
                    raise HTTPException(status_code=404, detail="Card not found")

                target_column = connection.execute(
                    "SELECT id FROM columns WHERE id = ?",
                    (operation.columnId,),
                ).fetchone()
                if not target_column:
                    raise HTTPException(status_code=404, detail="Target column not found")

                current_column_id = card_row["column_id"]
                now = utc_now()

                park_card_position(connection, operation.cardId)
                current_ids = fetch_card_ids(connection, current_column_id)
                if operation.cardId in current_ids:
                    current_ids.remove(operation.cardId)
                reorder_cards(connection, current_column_id, current_ids)

                target_ids = fetch_card_ids(connection, operation.columnId)
                insert_at = operation.position
                if insert_at is None:
                    insert_at = len(target_ids)
                insert_at = max(0, min(insert_at, len(target_ids)))
                target_ids.insert(insert_at, operation.cardId)
                connection.execute(
                    """
                    UPDATE cards
                    SET column_id = ?, position = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (operation.columnId, -1, now, operation.cardId),
                )
                reorder_cards(connection, operation.columnId, target_ids)
                continue

            if isinstance(operation, DeleteCardOp):
                row = connection.execute(
                    "SELECT id, column_id FROM cards WHERE id = ?",
                    (operation.cardId,),
                ).fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail="Card not found")
                connection.execute("DELETE FROM cards WHERE id = ?", (operation.cardId,))
                remaining_ids = fetch_card_ids(connection, row["column_id"])
                reorder_cards(connection, row["column_id"], remaining_ids)
                continue

            if isinstance(operation, UpdateBoardTitleOp):
                now = utc_now()
                connection.execute(
                    "UPDATE boards SET title = ?, updated_at = ? WHERE id = ?",
                    (operation.title, now, board_id),
                )
                connection.commit()

        connection.commit()
    except Exception:
        connection.rollback()
        raise

from __future__ import annotations

from contextlib import asynccontextmanager
import json
import os
from pathlib import Path
from typing import Annotated, Literal
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .db import ensure_user_and_board, get_connection, init_db, utc_now
from .openrouter import fetch_chat_completion

@asynccontextmanager
async def lifespan(_: FastAPI):
  init_db()
  yield


app = FastAPI(lifespan=lifespan)

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
INDEX_FILE = STATIC_DIR / "index.html"


class ColumnCreate(BaseModel):
  title: str
  position: int | None = None


class ColumnUpdate(BaseModel):
  title: str | None = None
  position: int | None = None


class CardCreate(BaseModel):
  column_id: str
  title: str
  details: str | None = None
  position: int | None = None


class CardUpdate(BaseModel):
  title: str | None = None
  details: str | None = None
  column_id: str | None = None
  position: int | None = None


class BoardUpdate(BaseModel):
  title: str


class LoginRequest(BaseModel):
  username: str
  password: str


class LoginResponse(BaseModel):
  status: str


class ChatMessage(BaseModel):
  role: Literal["system", "user", "assistant"]
  content: str


class CreateColumnOp(BaseModel):
  type: Literal["create_column"]
  title: str
  position: int | None = None


class RenameColumnOp(BaseModel):
  type: Literal["rename_column"]
  columnId: str
  title: str


class MoveColumnOp(BaseModel):
  type: Literal["move_column"]
  columnId: str
  position: int


class DeleteColumnOp(BaseModel):
  type: Literal["delete_column"]
  columnId: str


class CreateCardOp(BaseModel):
  type: Literal["create_card"]
  columnId: str
  title: str
  details: str | None = None
  position: int | None = None


class UpdateCardOp(BaseModel):
  type: Literal["update_card"]
  cardId: str
  title: str | None = None
  details: str | None = None


class MoveCardOp(BaseModel):
  type: Literal["move_card"]
  cardId: str
  columnId: str
  position: int | None = None


class DeleteCardOp(BaseModel):
  type: Literal["delete_card"]
  cardId: str


class UpdateBoardTitleOp(BaseModel):
  type: Literal["update_board_title"]
  title: str


ChatOperation = Annotated[
  (
    CreateColumnOp
    | RenameColumnOp
    | MoveColumnOp
    | DeleteColumnOp
    | CreateCardOp
    | UpdateCardOp
    | MoveCardOp
    | DeleteCardOp
    | UpdateBoardTitleOp
  ),
  Field(discriminator="type"),
]


class ChatModelOutput(BaseModel):
  reply: str
  operations: list[ChatOperation] = []


class ChatRequest(BaseModel):
  message: str
  conversation: list[ChatMessage] | None = None


class ChatResponse(BaseModel):
  reply: str
  operations: list[ChatOperation] = []


class ColumnResponse(BaseModel):
  id: str
  title: str
  position: int
  cardIds: list[str]


class CardResponse(BaseModel):
  id: str
  title: str
  details: str
  position: int
  columnId: str


class BoardResponse(BaseModel):
  id: str
  title: str
  columns: list[ColumnResponse]
  cards: dict[str, CardResponse]


def normalize_details(details: str | None) -> str:
  if details and details.strip():
    return details.strip()
  return "No details yet."


def fetch_column_ids(connection, board_id: str) -> list[str]:
  rows = connection.execute(
    "SELECT id FROM columns WHERE board_id = ? ORDER BY position",
    (board_id,),
  ).fetchall()
  return [row["id"] for row in rows]


def fetch_card_ids(connection, column_id: str) -> list[str]:
  rows = connection.execute(
    "SELECT id FROM cards WHERE column_id = ? ORDER BY position",
    (column_id,),
  ).fetchall()
  return [row["id"] for row in rows]


def reorder_columns(connection, board_id: str, ordered_ids: list[str]) -> None:
  now = utc_now()
  for index, column_id in enumerate(ordered_ids):
    connection.execute(
      "UPDATE columns SET position = ?, updated_at = ? WHERE id = ?",
      (-(index + 1), now, column_id),
    )
  for index, column_id in enumerate(ordered_ids):
    connection.execute(
      "UPDATE columns SET position = ?, updated_at = ? WHERE id = ?",
      (index, now, column_id),
    )
  connection.commit()


def park_card_position(connection, card_id: str) -> None:
  now = utc_now()
  connection.execute(
    "UPDATE cards SET position = ?, updated_at = ? WHERE id = ?",
    (-999999, now, card_id),
  )


def reorder_cards(connection, column_id: str, ordered_ids: list[str]) -> None:
  now = utc_now()
  min_row = connection.execute(
    "SELECT MIN(position) as min_pos FROM cards WHERE column_id = ?",
    (column_id,),
  ).fetchone()
  min_pos = min_row["min_pos"] if min_row and min_row["min_pos"] is not None else 0
  temp_start = min_pos - len(ordered_ids) - 1

  for index, card_id in enumerate(ordered_ids):
    temp_pos = temp_start + index
    connection.execute(
      "UPDATE cards SET position = ?, updated_at = ? WHERE id = ?",
      (temp_pos, now, card_id),
    )

  for index, card_id in enumerate(ordered_ids):
    connection.execute(
      "UPDATE cards SET position = ?, updated_at = ? WHERE id = ?",
      (index, now, card_id),
    )

  connection.commit()


def extract_json_payload(content: str) -> str:
  text = content.strip()
  fence_start = text.find("```")
  if fence_start == -1:
    return text
  fence_end = text.find("```", fence_start + 3)
  if fence_end == -1:
    return text
  fenced = text[fence_start + 3:fence_end].strip()
  if fenced.lower().startswith("json"):
    fenced = fenced[4:].strip()
  return fenced


def normalize_operation_keys(operation: dict[str, object]) -> dict[str, object]:
  normalized: dict[str, object] = {}
  for key, value in operation.items():
    clean_key = key.strip().rstrip(":")
    normalized[clean_key] = value
  return normalized


def normalize_move_card_target(
  operation: dict[str, object],
  board: BoardResponse,
) -> dict[str, object]:
  if "columnId" in operation:
    return operation

  candidates = [
    "toColumnId",
    "to_column_id",
    "toColumn",
    "to",
    "targetColumn",
    "targetColumnId",
    "target",
  ]
  for key in candidates:
    if key in operation:
      operation["columnId"] = operation[key]
      return operation

  title_keys = ["toColumnTitle", "toColumnName", "toTitle", "toName"]
  for key in title_keys:
    value = operation.get(key)
    if isinstance(value, str) and value.strip():
      target_title = value.strip().lower()
      for column in board.columns:
        if column.title.lower() == target_title:
          operation["columnId"] = column.id
          return operation
  return operation


def parse_model_output(content: str, board: BoardResponse) -> ChatModelOutput:
  raw = extract_json_payload(content)
  try:
    data = json.loads(raw)
  except json.JSONDecodeError as exc:
    return ChatModelOutput(reply=content.strip(), operations=[])

  if isinstance(data, dict):
    operations = data.get("operations")
    if isinstance(operations, list):
      for op in operations:
        if not isinstance(op, dict):
          continue
        normalized = normalize_operation_keys(op)
        if normalized.get("type") == "move_card":
          normalized = normalize_move_card_target(normalized, board)
        op.clear()
        op.update(normalized)

  try:
    return ChatModelOutput.model_validate(data)
  except ValueError as exc:
    return ChatModelOutput(reply=content.strip(), operations=[])


def build_chat_messages(payload: ChatRequest, board: BoardResponse) -> list[dict[str, str]]:
  system_message = (
    "You are an assistant for a kanban board. "
    "Return JSON only with this schema: "
    "{\"reply\": string, \"operations\": array}. "
    "Use exact keys: reply, operations, type, cardId, columnId, title, details, position. "
    "Valid operation types: create_column, rename_column, move_column, "
    "delete_column, create_card, update_card, move_card, delete_card, "
    "update_board_title. "
    "When no updates are needed, return an empty operations array."
  )
  context = {
    "board": board.model_dump(),
    "conversation": [msg.model_dump() for msg in (payload.conversation or [])],
    "message": payload.message,
  }
  user_message = json.dumps(context, indent=2)
  return [
    {"role": "system", "content": system_message},
    {"role": "user", "content": user_message},
  ]


def get_login_credentials() -> tuple[str, str]:
  username = os.getenv("PM_USERNAME", "jared")
  password = os.getenv("PM_PASSWORD", "password")
  return username, password


def apply_operations(connection, board_id: str, operations: list[ChatOperation]) -> None:
  if not operations:
    return

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


def build_board(connection, board_id: str) -> BoardResponse:
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

  card_ids_by_column: dict[str, list[str]] = {
    row["id"]: [] for row in column_rows
  }
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


@app.get("/api/health")
def read_health() -> dict[str, str]:
  return {"status": "ok"}


@app.post("/api/login", response_model=LoginResponse)
def login(payload: LoginRequest) -> LoginResponse:
  expected_username, expected_password = get_login_credentials()
  if payload.username == expected_username and payload.password == expected_password:
    return LoginResponse(status="ok")
  raise HTTPException(status_code=401, detail="Invalid credentials")


@app.get("/up", response_class=PlainTextResponse)
def read_up() -> str:
  return "OK"


@app.get("/api/board", response_model=BoardResponse)
def read_board() -> BoardResponse:
  connection = get_connection()
  try:
    board_id = ensure_user_and_board(connection)
    return build_board(connection, board_id)
  finally:
    connection.close()


@app.patch("/api/board", response_model=BoardResponse)
def update_board(payload: BoardUpdate) -> BoardResponse:
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


@app.post("/api/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest) -> ChatResponse:
  message = payload.message.strip()
  if not message:
    raise HTTPException(status_code=400, detail="Message is required")
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


@app.post("/api/columns", response_model=ColumnResponse)
def create_column(payload: ColumnCreate) -> ColumnResponse:
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
def update_column(column_id: str, payload: ColumnUpdate) -> ColumnResponse:
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
def delete_column(column_id: str) -> dict[str, str]:
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


@app.post("/api/cards", response_model=CardResponse)
def create_card(payload: CardCreate) -> CardResponse:
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
def update_card(card_id: str, payload: CardUpdate) -> CardResponse:
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
def delete_card(card_id: str) -> dict[str, str]:
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

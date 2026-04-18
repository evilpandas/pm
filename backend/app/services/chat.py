"""AI chat parsing and message building."""

from __future__ import annotations

import json

from ..models import BoardResponse, ChatModelOutput, ChatRequest


def extract_json_payload(content: str) -> str:
    """Extract JSON from markdown code fences if present."""
    text = content.strip()
    fence_start = text.find("```")
    if fence_start == -1:
        return text
    fence_end = text.find("```", fence_start + 3)
    if fence_end == -1:
        return text
    fenced = text[fence_start + 3 : fence_end].strip()
    if fenced.lower().startswith("json"):
        fenced = fenced[4:].strip()
    return fenced


def normalize_operation_keys(operation: dict[str, object]) -> dict[str, object]:
    """Normalize operation keys by stripping whitespace and trailing colons."""
    normalized: dict[str, object] = {}
    for key, value in operation.items():
        clean_key = key.strip().rstrip(":")
        normalized[clean_key] = value
    return normalized


def normalize_move_card_target(
    operation: dict[str, object],
    board: BoardResponse,
) -> dict[str, object]:
    """Normalize move_card operation to use columnId field.

    Handles various field names and column title lookups.
    """
    if "columnId" in operation:
        return operation

    # Try various column ID field names
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

    # Try column title lookups
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
    """Parse AI model output into structured ChatModelOutput.

    Handles JSON extraction, key normalization, and validation.
    """
    raw = extract_json_payload(content)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
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
    except ValueError:
        return ChatModelOutput(reply=content.strip(), operations=[])


def build_chat_messages(payload: ChatRequest, board: BoardResponse) -> list[dict[str, str]]:
    """Build messages list for AI chat API request."""
    system_message = (
        "You are an assistant for a kanban board. "
        "Return JSON only with this schema: "
        '{"reply": string, "operations": array}. '
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

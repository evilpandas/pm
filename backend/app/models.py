"""Request and response models for the PM MVP API."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field


# Request Models

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
    token: str


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


# Chat Operation Models

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


# Response Models

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

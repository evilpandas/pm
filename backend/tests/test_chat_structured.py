import json

from fastapi.testclient import TestClient

from app import main


def test_chat_applies_operations(tmp_path, monkeypatch):
  db_path = tmp_path / "test.db"
  monkeypatch.setenv("PM_DB_PATH", str(db_path))

  with TestClient(main.app) as client:
    board = client.get("/api/board").json()
    column_id = board["columns"][0]["id"]

    async def fake_fetch_chat_completion(messages):
      return json.dumps(
        {
          "reply": "Added a card.",
          "operations": [
            {
              "type": "create_card",
              "columnId": column_id,
              "title": "AI card",
              "details": "From the model",
              "position": 0,
            }
          ],
        }
      )

    monkeypatch.setattr(main, "fetch_chat_completion", fake_fetch_chat_completion)

    response = client.post("/api/chat", json={"message": "Add a card."})
    assert response.status_code == 200

    updated_board = client.get("/api/board").json()
    titles = [card["title"] for card in updated_board["cards"].values()]
    assert "AI card" in titles


def test_chat_accepts_to_column_id(tmp_path, monkeypatch):
  db_path = tmp_path / "test.db"
  monkeypatch.setenv("PM_DB_PATH", str(db_path))

  with TestClient(main.app) as client:
    board = client.get("/api/board").json()
    source_column = board["columns"][0]["id"]
    target_column = board["columns"][1]["id"]
    card_id = board["columns"][0]["cardIds"][0]

    async def fake_fetch_chat_completion(messages):
      return json.dumps(
        {
          "reply": "Moved the card.",
          "operations": [
            {
              "type": "move_card",
              "cardId": card_id,
              "toColumnId": target_column,
              "position": 0,
            }
          ],
        }
      )

    monkeypatch.setattr(main, "fetch_chat_completion", fake_fetch_chat_completion)

    response = client.post("/api/chat", json={"message": "Move a card."})
    assert response.status_code == 200

    updated_board = client.get("/api/board").json()
    updated_card = updated_board["cards"][card_id]
    assert updated_card["columnId"] == target_column


def test_chat_normalizes_move_card_fields(tmp_path, monkeypatch):
  db_path = tmp_path / "test.db"
  monkeypatch.setenv("PM_DB_PATH", str(db_path))

  with TestClient(main.app) as client:
    board = client.get("/api/board").json()
    target_column = board["columns"][1]
    card_id = board["columns"][0]["cardIds"][0]

    async def fake_fetch_chat_completion(messages):
      return json.dumps(
        {
          "reply": "Moved the card.",
          "operations": [
            {
              "type": "move_card",
              "cardId:": card_id,
              "toColumnTitle": target_column["title"],
              "position": 0,
            }
          ],
        }
      )

    monkeypatch.setattr(main, "fetch_chat_completion", fake_fetch_chat_completion)

    response = client.post("/api/chat", json={"message": "Move a card."})
    assert response.status_code == 200

    updated_board = client.get("/api/board").json()
    updated_card = updated_board["cards"][card_id]
    assert updated_card["columnId"] == target_column["id"]

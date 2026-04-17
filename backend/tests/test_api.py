import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("PM_DB_PATH", str(db_path))
    with TestClient(app) as test_client:
        yield test_client


def test_board_seeded_on_first_request(client):
    response = client.get("/api/board")
    assert response.status_code == 200
    payload = response.json()
    assert payload["title"] == "Kanban Studio"
    assert len(payload["columns"]) == 5
    assert len(payload["cards"]) == 8


def test_create_column(client):
    response = client.post("/api/columns", json={"title": "Blocked"})
    assert response.status_code == 200
    column = response.json()
    assert column["title"] == "Blocked"

    board = client.get("/api/board").json()
    column_ids = [item["id"] for item in board["columns"]]
    assert column["id"] in column_ids


def test_create_and_move_card(client):
    board = client.get("/api/board").json()
    source_column = board["columns"][0]["id"]
    target_column = board["columns"][1]["id"]

    create_response = client.post(
        "/api/cards",
        json={
            "column_id": source_column,
            "title": "Test card",
            "details": "Test details",
        },
    )
    assert create_response.status_code == 200
    card = create_response.json()

    move_response = client.patch(
        f"/api/cards/{card['id']}",
        json={"column_id": target_column, "position": 0},
    )
    assert move_response.status_code == 200
    moved_card = move_response.json()
    assert moved_card["columnId"] == target_column
    assert moved_card["position"] == 0


def test_update_board_title(client):
    response = client.patch("/api/board", json={"title": "My Board"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["title"] == "My Board"


def test_update_column_and_delete(client):
    create_response = client.post("/api/columns", json={"title": "Blocked"})
    assert create_response.status_code == 200
    column = create_response.json()

    update_response = client.patch(
        f"/api/columns/{column['id']}",
        json={"title": "Waiting", "position": 0},
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["title"] == "Waiting"
    assert updated["position"] == 0

    delete_response = client.delete(f"/api/columns/{column['id']}")
    assert delete_response.status_code == 200
    assert delete_response.json()["status"] == "ok"


def test_create_update_delete_card(client):
    board = client.get("/api/board").json()
    column_id = board["columns"][0]["id"]

    create_response = client.post(
        "/api/cards",
        json={"column_id": column_id, "title": "Card", "details": ""},
    )
    assert create_response.status_code == 200
    card = create_response.json()
    assert card["details"] == "No details yet."

    update_response = client.patch(
        f"/api/cards/{card['id']}",
        json={"title": "Updated", "details": "Details"},
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["title"] == "Updated"
    assert updated["details"] == "Details"

    delete_response = client.delete(f"/api/cards/{card['id']}")
    assert delete_response.status_code == 200
    assert delete_response.json()["status"] == "ok"


def test_not_found_errors(client):
    column_response = client.patch(
        "/api/columns/missing",
        json={"title": "Missing"},
    )
    assert column_response.status_code == 404

    card_response = client.patch(
        "/api/cards/missing",
        json={"title": "Missing"},
    )
    assert card_response.status_code == 404

    delete_response = client.delete("/api/cards/missing")
    assert delete_response.status_code == 404

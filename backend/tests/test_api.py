import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.auth import create_access_token
from app.config import reload_settings


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("PM_DB_PATH", str(db_path))
    monkeypatch.setenv("PM_USERNAME", "jared")
    monkeypatch.setenv("PM_PASSWORD", "test-passphrase")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-for-testing")
    reload_settings()
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def auth_headers():
    token = create_access_token({"sub": "jared"})
    return {"Authorization": f"Bearer {token}"}


def test_board_seeded_on_first_request(client, auth_headers):
    response = client.get("/api/board", headers=auth_headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["title"] == "Kanban Studio"
    assert len(payload["columns"]) == 5
    assert len(payload["cards"]) == 8


def test_up_route(client):
    response = client.get("/up")
    assert response.status_code == 200
    assert response.text == "OK"


def test_login_route(client, auth_headers):
    # First make a request to ensure user is created
    client.get("/api/board", headers=auth_headers)

    response = client.post(
        "/api/login",
        json={"username": "jared", "password": "test-passphrase"},
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    data = response.json()
    assert data["status"] == "ok"
    assert "token" in data

    bad_response = client.post(
        "/api/login",
        json={"username": "jared", "password": "wrong"},
    )
    assert bad_response.status_code == 401


def test_create_column(client, auth_headers):
    response = client.post("/api/columns", json={"title": "Blocked"}, headers=auth_headers)
    assert response.status_code == 200
    column = response.json()
    assert column["title"] == "Blocked"

    board = client.get("/api/board", headers=auth_headers).json()
    column_ids = [item["id"] for item in board["columns"]]
    assert column["id"] in column_ids


def test_create_and_move_card(client, auth_headers):
    board = client.get("/api/board", headers=auth_headers).json()
    source_column = board["columns"][0]["id"]
    target_column = board["columns"][1]["id"]

    create_response = client.post(
        "/api/cards",
        json={
            "column_id": source_column,
            "title": "Test card",
            "details": "Test details",
        },
        headers=auth_headers,
    )
    assert create_response.status_code == 200
    card = create_response.json()

    move_response = client.patch(
        f"/api/cards/{card['id']}",
        json={"column_id": target_column, "position": 0},
        headers=auth_headers,
    )
    assert move_response.status_code == 200
    moved_card = move_response.json()
    assert moved_card["columnId"] == target_column
    assert moved_card["position"] == 0


def test_update_board_title(client, auth_headers):
    response = client.patch("/api/board", json={"title": "My Board"}, headers=auth_headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["title"] == "My Board"


def test_update_column_and_delete(client, auth_headers):
    create_response = client.post("/api/columns", json={"title": "Blocked"}, headers=auth_headers)
    assert create_response.status_code == 200
    column = create_response.json()

    update_response = client.patch(
        f"/api/columns/{column['id']}",
        json={"title": "Waiting", "position": 0},
        headers=auth_headers,
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["title"] == "Waiting"
    assert updated["position"] == 0

    delete_response = client.delete(f"/api/columns/{column['id']}", headers=auth_headers)
    assert delete_response.status_code == 200
    assert delete_response.json()["status"] == "ok"


def test_create_update_delete_card(client, auth_headers):
    board = client.get("/api/board", headers=auth_headers).json()
    column_id = board["columns"][0]["id"]

    create_response = client.post(
        "/api/cards",
        json={"column_id": column_id, "title": "Card", "details": ""},
        headers=auth_headers,
    )
    assert create_response.status_code == 200
    card = create_response.json()
    assert card["details"] == "No details yet."

    update_response = client.patch(
        f"/api/cards/{card['id']}",
        json={"title": "Updated", "details": "Details"},
        headers=auth_headers,
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["title"] == "Updated"
    assert updated["details"] == "Details"

    delete_response = client.delete(f"/api/cards/{card['id']}", headers=auth_headers)
    assert delete_response.status_code == 200
    assert delete_response.json()["status"] == "ok"


def test_not_found_errors(client, auth_headers):
    column_response = client.patch(
        "/api/columns/missing",
        json={"title": "Missing"},
        headers=auth_headers,
    )
    assert column_response.status_code == 404

    card_response = client.patch(
        "/api/cards/missing",
        json={"title": "Missing"},
        headers=auth_headers,
    )
    assert card_response.status_code == 404

    delete_response = client.delete("/api/cards/missing", headers=auth_headers)
    assert delete_response.status_code == 404

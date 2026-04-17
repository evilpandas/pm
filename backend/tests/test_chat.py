import os

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.mark.skipif(
  not os.getenv("OPENROUTER_API_KEY"),
  reason="OPENROUTER_API_KEY not set",
)
def test_chat_endpoint_hits_openrouter(tmp_path, monkeypatch):
  db_path = tmp_path / "test.db"
  monkeypatch.setenv("PM_DB_PATH", str(db_path))

  with TestClient(app) as client:
    response = client.post(
      "/api/chat",
      json={"message": "What is 2+2? Reply with just the number."},
    )

  assert response.status_code == 200
  payload = response.json()
  assert payload["reply"].strip()
  assert "operations" in payload

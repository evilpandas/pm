from __future__ import annotations

import os
from typing import Any

import httpx
from fastapi import HTTPException

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = "openai/gpt-oss-120b"


async def fetch_chat_completion(messages: list[dict[str, Any]]) -> str:
  api_key = os.getenv("OPENROUTER_API_KEY")
  if not api_key:
    raise HTTPException(status_code=500, detail="OPENROUTER_API_KEY is not set")

  payload = {
    "model": OPENROUTER_MODEL,
    "messages": messages,
    "response_format": {"type": "json_object"},
    "temperature": 0.2,
  }
  headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json",
  }

  async with httpx.AsyncClient(timeout=20.0) as client:
    response = await client.post(OPENROUTER_URL, json=payload, headers=headers)

  if response.status_code >= 400:
    raise HTTPException(
      status_code=502,
      detail=(
        "OpenRouter error: "
        f"{response.status_code} "
        f"{response.text}"
      ),
    )

  data = response.json()
  choices = data.get("choices")
  if not choices:
    raise HTTPException(
      status_code=502,
      detail="OpenRouter response missing choices",
    )

  message_data = choices[0].get("message") if isinstance(choices[0], dict) else None
  content = message_data.get("content") if message_data else None
  if not content:
    raise HTTPException(
      status_code=502,
      detail="OpenRouter response missing message content",
    )

  return str(content).strip()

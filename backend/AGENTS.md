# Backend overview

## Stack

- FastAPI application served by Uvicorn
- Dependencies installed with uv from pyproject.toml inside Docker

## Entry point

- app/main.py defines the FastAPI app

## Current routes

- / serves the static frontend export when available
- /api/health returns JSON status
FROM node:20-slim AS frontend-build

WORKDIR /frontend

COPY frontend/package.json frontend/package-lock.json /frontend/
RUN npm ci

COPY frontend /frontend
RUN npm run build

FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN pip install --no-cache-dir uv

COPY backend/pyproject.toml /app/backend/pyproject.toml
COPY backend/uv.lock /app/backend/uv.lock
RUN uv export --frozen --project /app/backend --format requirements-txt --output-file /tmp/requirements.txt
RUN uv pip install --system -r /tmp/requirements.txt

COPY backend /app/backend
COPY --from=frontend-build /frontend/out /app/backend/static

RUN addgroup --system --gid 1001 appuser && \
    adduser --system --uid 1001 --ingroup appuser appuser && \
    chown -R appuser:appuser /app && \
    mkdir -p /app/.cache && \
    chown -R appuser:appuser /app/.cache

ENV UV_CACHE_DIR=/app/.cache/uv

USER appuser

EXPOSE 80

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "80"]

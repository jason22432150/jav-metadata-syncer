# ─── Stage 1: build the React frontend ────────────────────────────────
FROM node:24-alpine AS frontend-build
WORKDIR /build
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# ─── Stage 2: Python runtime + static files ───────────────────────────
FROM python:3.12-slim AS runtime
WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libxml2 libxslt1.1 ca-certificates tzdata curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
COPY --from=frontend-build /build/dist ./static

# Persisted runtime settings live in /app/data
RUN mkdir -p /app/data
VOLUME ["/app/data"]

ENV CORS_ORIGINS=* \
    DATA_DIR=/app/data \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Taipei

EXPOSE 7712

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS http://127.0.0.1:7712/api/health || exit 1

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7712", "--workers", "1"]

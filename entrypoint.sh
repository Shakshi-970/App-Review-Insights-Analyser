#!/bin/bash
set -e

# Decode Google credentials from base64 env var (set in HF Space secrets).
# This keeps credentials.json out of the Docker image and git history.
if [ -n "$GOOGLE_CREDENTIALS_BASE64" ]; then
    echo "$GOOGLE_CREDENTIALS_BASE64" | base64 -d > /app/credentials.json
    echo "[entrypoint] credentials.json written from GOOGLE_CREDENTIALS_BASE64"
fi

# HuggingFace Spaces requires port 7860; fallback to 8080 for local dev.
exec uvicorn src.portal.app:app --host 0.0.0.0 --port "${PORT:-7860}"

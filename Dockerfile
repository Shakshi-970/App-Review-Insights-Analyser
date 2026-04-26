FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-bake the sentence-transformers model into the image so there are no
# network calls at runtime (avoids cold-start failures and proxy issues).
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

COPY src/ ./src/
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

ENV HF_HUB_OFFLINE=1
ENV TRANSFORMERS_OFFLINE=1
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV PYTHONIOENCODING=utf-8

# HuggingFace Spaces requires port 7860.
# For local dev or Railway, override via PORT env var.
EXPOSE 7860

ENTRYPOINT ["./entrypoint.sh"]

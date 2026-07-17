# CPU-only backend image. Model inference (BGE-M3 embeddings, cross-encoder
# reranking) runs on CPU inside the container -- slower than the GPU setup
# used during development, but far simpler to deploy and works on any machine
# without needing NVIDIA Container Toolkit / GPU passthrough.

FROM python:3.11-slim

WORKDIR /app

# System deps needed by some ML packages (sentencepiece, tokenizers) to build/run correctly
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# NOTE: model weights are NOT pre-downloaded here -- see backend/Dockerfile
# for the full explanation (image size limits on Railway). Models download
# at runtime on first startup instead. For local Docker Compose use, the
# host's Hugging Face cache can optionally be mounted as a volume to avoid
# re-downloading on every container rebuild (see docker-compose.yml).

COPY . .

EXPOSE 8000

# Uses shell form so ${PORT} gets substituted -- Railway (and most cloud
# platforms) assign a dynamic port via this env var; falls back to 8000
# for local Docker Compose use where PORT isn't set.
CMD sh -c "uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}"
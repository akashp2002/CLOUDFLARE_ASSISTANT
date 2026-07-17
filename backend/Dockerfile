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

# Pre-download the embedding + reranker model weights INTO the image at build
# time. This avoids two problems seen during development:
#   1. Slow/unreliable downloads happening at container startup over the
#      network (the RemoteDisconnected errors from Hugging Face)
#   2. Slow repeated reads through a Windows-to-WSL2 bind-mounted cache
#      folder at runtime
# The download happens once, here, and gets cached as a Docker image layer --
# subsequent builds skip this step entirely unless requirements.txt changes.
RUN python -c "\
from FlagEmbedding import BGEM3FlagModel; \
BGEM3FlagModel('BAAI/bge-m3', use_fp16=False); \
print('BGE-M3 downloaded.')"
RUN python -c "\
from FlagEmbedding import FlagReranker; \
FlagReranker('BAAI/bge-reranker-v2-m3', use_fp16=False); \
print('Reranker downloaded.')"

COPY . .

EXPOSE 8000

# Uses shell form so ${PORT} gets substituted -- Railway (and most cloud
# platforms) assign a dynamic port via this env var; falls back to 8000
# for local Docker Compose use where PORT isn't set.
CMD sh -c "uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}"
"""
Phase 5: Store embeddings in Qdrant
-------------------------------------
Reads the chunks + embeddings from data/embeddings/chunks_with_embeddings.json
(Phase 4 output), creates a Qdrant collection sized for BGE-M3's dense vectors
(1024 dimensions), and uploads every chunk as a "point" -- Qdrant's term for one
stored vector + its associated payload (our chunk text + metadata).

Assumes Qdrant is already running locally via Docker on localhost:6333.

Install first:
    pip install qdrant-client
"""

import json
from pathlib import Path

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

EMBEDDINGS_PATH = Path("data/embeddings/chunks_with_embeddings.json")

QDRANT_HOST = "localhost"
QDRANT_PORT = 6333
COLLECTION_NAME = "cloudflare_incidents"
VECTOR_DIM = 1024  # BGE-M3's dense embedding size, confirmed in Phase 4's output

UPLOAD_BATCH_SIZE = 50  # how many points to upload per request


def load_chunks_with_embeddings() -> list[dict]:
    if not EMBEDDINGS_PATH.exists():
        raise FileNotFoundError(f"Expected {EMBEDDINGS_PATH} -- run Phase 4 first.")

    with open(EMBEDDINGS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    chunks = load_chunks_with_embeddings()
    print(f"Loaded {len(chunks)} chunks with embeddings.")

    client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

    # Create the collection. recreate_collection wipes it first if it already exists --
    # convenient while iterating on your pipeline, since re-running this script gives
    # you a clean slate each time instead of duplicate/stale points.
    client.recreate_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=VECTOR_DIM, distance=Distance.COSINE),
    )
    print(f"Created collection '{COLLECTION_NAME}' (dim={VECTOR_DIM}, distance=cosine).")

    # Build Qdrant "points" -- each point needs a unique id, the vector itself,
    # and a "payload" (arbitrary metadata stored alongside the vector, which
    # Qdrant returns to you on search -- this is how we get chunk text + citations
    # back later without a separate lookup).
    points = []
    for i, chunk in enumerate(chunks):
        points.append(
            PointStruct(
                id=i,  # Qdrant needs a unique int or UUID per point -- sequential int is simplest here
                vector=chunk["embedding"],
                payload={
                    "text": chunk["text"],
                    "chunk_id": chunk.get("node_id", ""),
                    "section_heading": chunk["metadata"].get("section_heading", ""),
                    "doc_id": chunk["metadata"].get("doc_id", ""),
                    "title": chunk["metadata"].get("title", ""),
                    "source_url": chunk["metadata"].get("source_url", ""),
                    "date": chunk["metadata"].get("date", ""),
                },
            )
        )

    print(f"Uploading {len(points)} points in batches of {UPLOAD_BATCH_SIZE}...")
    for start in range(0, len(points), UPLOAD_BATCH_SIZE):
        batch = points[start:start + UPLOAD_BATCH_SIZE]
        client.upsert(collection_name=COLLECTION_NAME, points=batch)
        print(f"  Uploaded {start + len(batch)}/{len(points)}")

    # Sanity check -- ask Qdrant how many points actually landed in the collection
    count = client.count(collection_name=COLLECTION_NAME).count
    print(f"\nDone. Collection '{COLLECTION_NAME}' now contains {count} points.")


if __name__ == "__main__":
    main()
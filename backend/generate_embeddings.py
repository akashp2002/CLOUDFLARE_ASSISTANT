"""
Phase 4: Embedding generation (BGE-M3)
----------------------------------------
Reads the chunks from data/chunks/nodes.json (Phase 3 output), generates a dense
embedding vector for each chunk's text using BAAI's BGE-M3 model, and saves the
chunks + their embeddings together -- ready for Phase 5 (storing in Qdrant).

BGE-M3 also supports sparse (lexical) and multi-vector embeddings, which is why
it's a good fit for hybrid retrieval later (Phase 6) -- but for this phase we
generate the dense embedding, since that's what powers standard vector search.

Install first:
    pip install FlagEmbedding torch --index-url https://download.pytorch.org/whl/cu121
"""

import json
from pathlib import Path

# from FlagEmbedding import BGEM3FlagModel
from FlagEmbedding import FlagModel

CHUNKS_DIR = Path("data/chunks")
EMBEDDINGS_DIR = Path("data/embeddings")
EMBEDDINGS_DIR.mkdir(parents=True, exist_ok=True)

BATCH_SIZE = 12  # how many chunks to embed at once -- tune down if you hit GPU memory errors


def load_chunks() -> list[dict]:
    nodes_path = CHUNKS_DIR / "nodes.json"
    if not nodes_path.exists():
        raise FileNotFoundError(f"Expected {nodes_path} -- run Phase 3 first.")

    with open(nodes_path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    chunks = load_chunks()
    print(f"Loaded {len(chunks)} chunks.")

    print("Loading BGE-M3 model (first run downloads ~2GB, please be patient)...")
    # use_fp16=True halves memory usage and speeds up inference on GPU, with negligible quality loss
    # model = BGEM3FlagModel("BAAI/bge-m3", use_fp16=True)
    # print("Model loaded.")
    print("Loading BGE-small model...")

    model = FlagModel(
    "BAAI/bge-small-en-v1.5",
    use_fp16=False
    )

    texts = [chunk["text"] for chunk in chunks]

    print(f"Generating embeddings for {len(texts)} chunks (batch size {BATCH_SIZE})...")
    # output = model.encode(
    #     texts,
    #     batch_size=BATCH_SIZE,
    #     max_length=1024,  # generous ceiling -- covers even our largest sub-split chunks safely
    #     return_dense=True,
    #     return_sparse=False,   # sparse vectors come in Phase 6 (hybrid retrieval), not needed yet
    #     return_colbert_vecs=False,
    # )

    # dense_vectors = output["dense_vecs"]  # one vector per chunk, same order as `texts`
    dense_vectors = []

    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i:i + BATCH_SIZE]
        print(f"Encoding batch {i} to {i + len(batch) - 1}")

        try:
            embeddings = model.encode(
                batch
            )
            dense_vectors.extend(embeddings)
        except Exception as e:
            print(f"\nError in batch starting at index {i}")
            for j, text in enumerate(batch):
                print(f"Chunk {i+j}: length={len(text)}")
                print(repr(text[:200]))
                print("-" * 50)
            raise
    # Attach each chunk's embedding back onto its own dict
    for chunk, vector in zip(chunks, dense_vectors):
        # chunk["embedding"] = vector.tolist()  # numpy array -> plain list, so it's JSON-serializable
        chunk["embedding"] = (
        vector.tolist() if hasattr(vector, "tolist") else vector
        )

    out_path = EMBEDDINGS_DIR / "chunks_with_embeddings.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(chunks, f)  # no indent -- embedding arrays make pretty-printing huge and pointless

    print(f"\nSaved {len(chunks)} chunks with embeddings to {out_path}")


if __name__ == "__main__":
    main()
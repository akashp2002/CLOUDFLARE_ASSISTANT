"""
Phase 6: Hybrid retrieval (Vector + BM25)
---------------------------------------------
Combines two retrieval methods for every query:
  1. Vector search (Qdrant)  -- good at matching meaning/topic, even with different wording
  2. BM25 (keyword search)   -- good at matching exact words, numbers, names

Results from both are merged using Reciprocal Rank Fusion (RRF), which combines
rankings (not raw scores, since cosine similarity and BM25 scores aren't on the
same scale and can't be directly compared/averaged).

Install first:
    pip install qdrant-client rank-bm25 FlagEmbedding
"""

import json
import os
from pathlib import Path
from dotenv import load_dotenv


from qdrant_client import QdrantClient
from rank_bm25 import BM25Okapi
# from FlagEmbedding import 
from FlagEmbedding import FlagModel
from langsmith import traceable

EMBEDDINGS_PATH = Path("data/embeddings/chunks_with_embeddings.json")
load_dotenv()


# Qdrant Cloud connection (preferred if set) -- falls back to local
# host/port connection for local Docker/dev use if QDRANT_URL isn't set.
QDRANT_URL = os.environ.get("QDRANT_URL")
QDRANT_API_KEY = os.environ.get("QDRANT_API_KEY")
QDRANT_HOST = os.environ.get("QDRANT_HOST", "localhost")  # "qdrant" when run via Docker Compose
QDRANT_PORT = 6333
COLLECTION_NAME = "cloudflare_incidents_bge_small"

TOP_K_EACH = 10   # how many results to pull from EACH method before fusing
TOP_K_FINAL = 5   # how many fused results to return at the end
RRF_K = 60        # standard RRF damping constant -- higher = flatter weighting across ranks


class HybridRetriever:
    def __init__(self):
        print("Loading chunk data (for BM25 indexing)...")
        with open(EMBEDDINGS_PATH, "r", encoding="utf-8") as f:
            self.chunks = json.load(f)

        # BM25 needs "tokenized" text -- a simple lowercase word split is enough here.
        # This is intentionally simple; you can swap in a smarter tokenizer later if needed.
        tokenized_corpus = [chunk["text"].lower().split() for chunk in self.chunks]
        self.bm25 = BM25Okapi(tokenized_corpus)
        print(f"BM25 index built over {len(self.chunks)} chunks.")

        # print("Loading BGE-M3 model for query embedding...")
        # self.embed_model = BGEM3FlagModel("BAAI/bge-m3", use_fp16=True)
        print("Loading BGE-small model for query embedding...")
        self.embed_model = FlagModel(
            "BAAI/bge-small-en-v1.5",
            use_fp16=False
        )
        print("Connecting to Qdrant...")
        if QDRANT_URL:
            self.qdrant = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
        else:
            self.qdrant = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
        print("HybridRetriever ready.\n")

    @traceable(name="vector_search", run_type="retriever")
    def vector_search(self, query: str, top_k: int = TOP_K_EACH) -> list[dict]:
        """Embeds the query and searches Qdrant for the closest chunk vectors."""
        # query_vector = self.embed_model.encode([query], return_dense=True)["dense_vecs"][0].tolist()
        query_vector = self.embed_model.encode([query])[0].tolist()

        response = self.qdrant.query_points(
            collection_name=COLLECTION_NAME,
            query=query_vector,
            limit=top_k,
        )
        results = response.points
        # Return each result's chunk_id (from payload) and its rank position (0 = best)
        return [{"chunk_id": r.payload["chunk_id"], "payload": r.payload} for r in results]

    @traceable(name="bm25_search", run_type="retriever")
    def bm25_search(self, query: str, top_k: int = TOP_K_EACH) -> list[dict]:
        """Scores every chunk against the query using BM25 and returns the top matches."""
        tokenized_query = query.lower().split()
        scores = self.bm25.get_scores(tokenized_query)

        # Pair each chunk with its score, sort descending, take top_k
        scored_chunks = sorted(
            zip(self.chunks, scores), key=lambda pair: pair[1], reverse=True
        )[:top_k]

        return [
            {"chunk_id": chunk.get("node_id", ""), "payload": {
                "text": chunk["text"],
                "chunk_id": chunk.get("node_id", ""),
                "section_heading": chunk["metadata"].get("section_heading", ""),
                "doc_id": chunk["metadata"].get("doc_id", ""),
                "title": chunk["metadata"].get("title", ""),
                "source_url": chunk["metadata"].get("source_url", ""),
            }}
            for chunk, score in scored_chunks
        ]

    @traceable(name="hybrid_search", run_type="chain")
    def hybrid_search(self, query: str, top_k: int = TOP_K_FINAL) -> list[dict]:
        """
        Runs both vector and BM25 search, then fuses the two ranked lists using
        Reciprocal Rank Fusion (RRF). For each chunk, RRF score = sum over every
        list it appears in of 1 / (RRF_K + rank_in_that_list). Chunks that rank
        highly in BOTH lists end up with the highest combined score.
        """
        vector_results = self.vector_search(query)
        bm25_results = self.bm25_search(query)

        rrf_scores: dict[str, float] = {}
        payload_lookup: dict[str, dict] = {}

        for rank, result in enumerate(vector_results):
            cid = result["chunk_id"]
            rrf_scores[cid] = rrf_scores.get(cid, 0) + 1 / (RRF_K + rank)
            payload_lookup[cid] = result["payload"]

        for rank, result in enumerate(bm25_results):
            cid = result["chunk_id"]
            rrf_scores[cid] = rrf_scores.get(cid, 0) + 1 / (RRF_K + rank)
            payload_lookup.setdefault(cid, result["payload"])

        ranked_chunk_ids = sorted(rrf_scores, key=lambda cid: rrf_scores[cid], reverse=True)[:top_k]

        return [
            {"chunk_id": cid, "rrf_score": rrf_scores[cid], "payload": payload_lookup[cid]}
            for cid in ranked_chunk_ids
        ]


if __name__ == "__main__":
    retriever = HybridRetriever()

    test_query = "How many Gbps of traffic were discarded during the Miami route leak?"
    print(f"Query: {test_query}\n")

    results = retriever.hybrid_search(test_query)
    for i, r in enumerate(results, 1):
        print(f"--- Result {i} (RRF score: {r['rrf_score']:.4f}) ---")
        print(f"Title: {r['payload'].get('title', '')}")
        print(f"Section: {r['payload'].get('section_heading', '')}")
        print(f"Text preview: {r['payload'].get('text', '')[:200]}...")
        print()

    # Verification: confirm the exact "12Gbps" figure actually appears in one of the
    # retrieved chunks -- this confirms BM25 (the keyword-matching half of hybrid search)
    # successfully caught a precise number, not just a general topic match.
    print("=== Verification: checking for exact figure match ===")
    found = False
    for r in results:
        if "12Gbps" in r["payload"]["text"] or "12 Gbps" in r["payload"]["text"]:
            print(f"FOUND the exact figure in: {r['payload']['title']} - {r['payload']['section_heading']}")
            found = True
    if not found:
        print("The exact figure was NOT found in any of the top results.")
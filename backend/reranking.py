"""
Phase 7: Cross-encoder reranking
------------------------------------
Takes the candidate chunks from Phase 6's hybrid retrieval and re-scores them
using a cross-encoder model (BAAI/bge-reranker-v2-m3), which reads the query
and each chunk TOGETHER (unlike the bi-encoder used for vector search, which
scores them separately). This is slower but far more precise, so we only run
it on the small shortlist hybrid retrieval already narrowed things down to --
not the full 290-chunk corpus.

Install first:
    pip install FlagEmbedding
"""

from hybrid_retrieval import HybridRetriever
from FlagEmbedding import FlagReranker
from langsmith import traceable

RERANK_CANDIDATES = 10   # how many chunks to pull from hybrid retrieval before reranking
FINAL_TOP_N = 3          # how many reranked chunks to keep for the LLM (Phase 8)


class RerankingRetriever:
    def __init__(self):
        # Reuse everything already built in Phase 6 -- BM25 index, embedding model, Qdrant connection
        self.hybrid_retriever = HybridRetriever()

        print("Loading cross-encoder reranker (BAAI/bge-reranker-v2-m3)...")

        # self.reranker = FlagReranker("BAAI/bge-reranker-base",use_fp16=False)
        self.reranker = None
        # print("Reranker ready.\n")
        print("Reranker is skipping.\n")


    @traceable(name="retrieve_and_rerank", run_type="chain")
    def retrieve_and_rerank(self, query: str, top_n: int = FINAL_TOP_N) -> list[dict]:
        # Step 1: get a shortlist of candidates from hybrid retrieval (fast, approximate)
        candidates = self.hybrid_retriever.hybrid_search(query, top_k=RERANK_CANDIDATES)

        if not candidates:
            return []

        # # Step 2: build (query, chunk_text) pairs -- the cross-encoder scores each pair jointly
        # pairs = [[query, c["payload"]["text"]] for c in candidates]

        # # Step 3: get one relevance score per pair directly from the cross-encoder
        # scores = self.reranker.compute_score(pairs, normalize=True)  # normalize -> scores in [0, 1]

        # # compute_score returns a single float (not a list) if there's only one pair -- handle both cases
        # if isinstance(scores, float):
        #     scores = [scores]

        # # Step 4: attach the rerank score to each candidate and sort by it, best first
        # for candidate, score in zip(candidates, scores):
        #     candidate["rerank_score"] = score

        # reranked = sorted(candidates, key=lambda c: c["rerank_score"], reverse=True)

        # return reranked[:top_n]
        return candidates[:top_n]


if __name__ == "__main__":
    retriever = RerankingRetriever()

    test_query = "How many Gbps of traffic were discarded during the Miami route leak?"
    print(f"Query: {test_query}\n")

    results = retriever.retrieve_and_rerank(test_query)
    for i, r in enumerate(results, 1):
        print(f"--- Reranked Result {i} (rerank score: {r['rerank_score']:.4f}, "
              f"original RRF score: {r['rrf_score']:.4f}) ---")
        print(f"Title: {r['payload'].get('title', '')}")
        print(f"Section: {r['payload'].get('section_heading', '')}")
        print(f"Text preview: {r['payload'].get('text', '')[:200]}...")
        print()
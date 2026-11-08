"""
evaluate_retrieval.py
---------------------
Quantitative Information Retrieval (IR) Evaluation for Cloudflare Incident RAG.

Measures:
  - Precision@K (P@1, P@3, P@5, P@10)
  - Recall@K (R@1, R@3, R@5, R@10)
  - MRR (Mean Reciprocal Rank)
  - NDCG@K (Normalized Discounted Cumulative Gain @ 1, 3, 5, 10)
  - Hit Rate @ K (Hit@1, Hit@3, Hit@5, Hit@10)

Evaluates and compares retrieval strategies side-by-side:
  1. BM25 Search (sparse lexical retrieval)
  2. Vector Search (dense BGE-small semantic retrieval via Qdrant)
  3. Hybrid Search (Reciprocal Rank Fusion - RRF combining Vector + BM25)
  4. Pipeline / Reranked output (top chunks delivered to generation)

Both Chunk-level (exact passage match) and Document-level (correct postmortem)
relevance are evaluated.

Outputs:
  - Formatted terminal comparison table
  - data/eval/retrieval_metrics_summary.json
  - data/eval/retrieval_metrics_summary.csv
  - data/eval/retrieval_query_diagnostics.json (per-query diagnostics & hard queries)
"""

import argparse
import csv
import json
import math
import os
import sys
import time
from pathlib import Path

# Silence LangSmith tracing during offline evaluation to prevent network overhead and 403 error spam
os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ["LANGSMITH_TRACING"] = "false"

from hybrid_retrieval import HybridRetriever
from reranking import RerankingRetriever

EVAL_DATASET_PATH = Path("data/eval/eval_dataset.json")
RESULTS_DIR = Path("data/eval")
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_K_VALUES = [1, 3, 5, 10]


def precision_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    """Calculates Precision@K = (relevant in top K) / K."""
    if k <= 0:
        return 0.0
    top_k = retrieved[:k]
    hits = sum(1 for item in top_k if item in relevant)
    return hits / k


def recall_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    """Calculates Recall@K = (relevant in top K) / (total relevant)."""
    if not relevant:
        return 0.0
    top_k = retrieved[:k]
    hits = sum(1 for item in top_k if item in relevant)
    return hits / len(relevant)


def reciprocal_rank(retrieved: list[str], relevant: set[str], max_k: int = 10) -> float:
    """Calculates Reciprocal Rank: 1 / rank of first relevant item in top max_k (or 0)."""
    for rank, item in enumerate(retrieved[:max_k], start=1):
        if item in relevant:
            return 1.0 / rank
    return 0.0


def dcg_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    """Discounted Cumulative Gain for binary relevance."""
    dcg = 0.0
    for i, item in enumerate(retrieved[:k], start=1):
        if item in relevant:
            dcg += 1.0 / math.log2(i + 1)
    return dcg


def ndcg_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    """Normalized Discounted Cumulative Gain @ K."""
    if not relevant or k <= 0:
        return 0.0
    actual_dcg = dcg_at_k(retrieved, relevant, k)
    ideal_num = min(k, len(relevant))
    idcg = sum(1.0 / math.log2(i + 1) for i in range(1, ideal_num + 1))
    return (actual_dcg / idcg) if idcg > 0 else 0.0


def hit_rate_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    """Hit Rate @ K = 1 if at least one relevant item in top K, else 0."""
    top_k = retrieved[:k]
    return 1.0 if any(item in relevant for item in top_k) else 0.0


def evaluate_query(
    query_item: dict,
    retriever: HybridRetriever,
    reranker: RerankingRetriever,
    k_values: list[int],
    max_k: int = 10
) -> dict:
    """
    Runs one query through BM25, Vector, Hybrid, and Pipeline retrieval,
    and returns metrics for both chunk-level and document-level ground truth.
    """
    question = query_item["question"]
    doc_id = query_item["source_doc_id"]
    relevant_chunks = set(query_item.get("relevant_chunk_ids", []))

    # Run retrievals
    t0 = time.time()
    bm25_results = retriever.bm25_search(question, top_k=max_k)
    t_bm25 = time.time() - t0

    t0 = time.time()
    vector_results = retriever.vector_search(question, top_k=max_k)
    t_vector = time.time() - t0

    t0 = time.time()
    hybrid_results = retriever.hybrid_search(question, top_k=max_k)
    t_hybrid = time.time() - t0

    t0 = time.time()
    pipeline_results = reranker.retrieve_and_rerank(question, top_n=max_k)
    t_pipeline = time.time() - t0

    # Extract retrieved chunk IDs and doc IDs
    methods = {
        "BM25": {
            "chunk_ids": [r["chunk_id"] for r in bm25_results],
            "doc_ids": [r["payload"].get("doc_id", "") for r in bm25_results],
            "latency_ms": round(t_bm25 * 1000, 2)
        },
        "Vector": {
            "chunk_ids": [r["chunk_id"] for r in vector_results],
            "doc_ids": [r["payload"].get("doc_id", "") for r in vector_results],
            "latency_ms": round(t_vector * 1000, 2)
        },
        "Hybrid": {
            "chunk_ids": [r["chunk_id"] for r in hybrid_results],
            "doc_ids": [r["payload"].get("doc_id", "") for r in hybrid_results],
            "latency_ms": round(t_hybrid * 1000, 2)
        },
        "Reranked": {
            "chunk_ids": [r["chunk_id"] for r in pipeline_results],
            "doc_ids": [r["payload"].get("doc_id", "") for r in pipeline_results],
            "latency_ms": round(t_pipeline * 1000, 2)
        }
    }

    query_metrics = {
        "question": question,
        "source_doc_id": doc_id,
        "relevant_chunks_count": len(relevant_chunks),
        "methods": {}
    }

    for method_name, data in methods.items():
        retrieved_chunks = data["chunk_ids"]
        retrieved_docs = data["doc_ids"]

        # Chunk-level metrics
        chunk_mrr = reciprocal_rank(retrieved_chunks, relevant_chunks, max_k=max_k)
        chunk_p = {f"P@{k}": precision_at_k(retrieved_chunks, relevant_chunks, k) for k in k_values}
        chunk_r = {f"R@{k}": recall_at_k(retrieved_chunks, relevant_chunks, k) for k in k_values}
        chunk_ndcg = {f"NDCG@{k}": ndcg_at_k(retrieved_chunks, relevant_chunks, k) for k in k_values}
        chunk_hit = {f"Hit@{k}": hit_rate_at_k(retrieved_chunks, relevant_chunks, k) for k in k_values}

        # Document-level metrics (evaluating whether the target incident document is retrieved)
        target_doc_id = doc_id
        doc_mrr = reciprocal_rank(retrieved_docs, {target_doc_id}, max_k=max_k)
        # Precision@K: fraction of top-K chunks that belong to the target document
        doc_p = {f"P@{k}": precision_at_k(retrieved_docs, {target_doc_id}, k) for k in k_values}
        # Recall@K / Hit@K: is the target document retrieved anywhere in top-K (binary 1.0 or 0.0)
        doc_r = {f"R@{k}": (1.0 if target_doc_id in retrieved_docs[:k] else 0.0) for k in k_values}
        # NDCG@K for target document discovery (rank of first appearance)
        def doc_ndcg_at_k(doc_list, target, k_val):
            for rank, d in enumerate(doc_list[:k_val], start=1):
                if d == target:
                    return 1.0 / math.log2(rank + 1)
            return 0.0
        doc_ndcg = {f"NDCG@{k}": doc_ndcg_at_k(retrieved_docs, target_doc_id, k) for k in k_values}
        doc_hit = {f"Hit@{k}": (1.0 if target_doc_id in retrieved_docs[:k] else 0.0) for k in k_values}

        query_metrics["methods"][method_name] = {
            "latency_ms": data["latency_ms"],
            "retrieved_chunk_ids": retrieved_chunks[:5],
            "retrieved_doc_ids": retrieved_docs[:5],
            "chunk_level": {
                "MRR": chunk_mrr,
                **chunk_p,
                **chunk_r,
                **chunk_ndcg,
                **chunk_hit
            },
            "doc_level": {
                "MRR": doc_mrr,
                **doc_p,
                **doc_r,
                **doc_ndcg,
                **doc_hit
            }
        }

    return query_metrics


def aggregate_metrics(all_query_metrics: list[dict], k_values: list[int]) -> dict:
    """Aggregates per-query metrics into mean scores for each method and granularity."""
    method_names = ["BM25", "Vector", "Hybrid", "Reranked"]
    n = len(all_query_metrics)
    if n == 0:
        return {}

    summary = {
        "num_queries": n,
        "k_values": k_values,
        "chunk_level": {},
        "doc_level": {},
        "latency_ms": {}
    }

    for method in method_names:
        # Latency
        avg_lat = sum(m["methods"][method]["latency_ms"] for m in all_query_metrics) / n
        summary["latency_ms"][method] = round(avg_lat, 2)

        # Chunk level
        chunk_agg = {
            "MRR": sum(m["methods"][method]["chunk_level"]["MRR"] for m in all_query_metrics) / n
        }
        for k in k_values:
            chunk_agg[f"P@{k}"] = sum(m["methods"][method]["chunk_level"][f"P@{k}"] for m in all_query_metrics) / n
            chunk_agg[f"R@{k}"] = sum(m["methods"][method]["chunk_level"][f"R@{k}"] for m in all_query_metrics) / n
            chunk_agg[f"NDCG@{k}"] = sum(m["methods"][method]["chunk_level"][f"NDCG@{k}"] for m in all_query_metrics) / n
            chunk_agg[f"Hit@{k}"] = sum(m["methods"][method]["chunk_level"][f"Hit@{k}"] for m in all_query_metrics) / n

        summary["chunk_level"][method] = {k: round(v, 4) for k, v in chunk_agg.items()}

        # Doc level
        doc_agg = {
            "MRR": sum(m["methods"][method]["doc_level"]["MRR"] for m in all_query_metrics) / n
        }
        for k in k_values:
            doc_agg[f"P@{k}"] = sum(m["methods"][method]["doc_level"][f"P@{k}"] for m in all_query_metrics) / n
            doc_agg[f"R@{k}"] = sum(m["methods"][method]["doc_level"][f"R@{k}"] for m in all_query_metrics) / n
            doc_agg[f"NDCG@{k}"] = sum(m["methods"][method]["doc_level"][f"NDCG@{k}"] for m in all_query_metrics) / n
            doc_agg[f"Hit@{k}"] = sum(m["methods"][method]["doc_level"][f"Hit@{k}"] for m in all_query_metrics) / n

        summary["doc_level"][method] = {k: round(v, 4) for k, v in doc_agg.items()}

    return summary


def format_table(title: str, metrics_dict: dict, k_values: list[int]) -> str:
    """Formats metrics dictionary into an ASCII comparison table."""
    methods = ["BM25", "Vector", "Hybrid", "Reranked"]
    lines = []
    lines.append(f"\n=== {title} ===")

    # Order of metrics to display
    display_keys = ["MRR"]
    for k in k_values:
        display_keys.append(f"P@{k}")
    for k in k_values:
        display_keys.append(f"R@{k}")
    for k in k_values:
        display_keys.append(f"NDCG@{k}")
    for k in k_values:
        display_keys.append(f"Hit@{k}")

    header = f"{'Metric':<14} | " + " | ".join(f"{m:>10}" for m in methods)
    divider = "-" * len(header)
    lines.append(divider)
    lines.append(header)
    lines.append(divider)

    for key in display_keys:
        row_vals = []
        for m in methods:
            val = metrics_dict[m].get(key, 0.0)
            row_vals.append(f"{val:>10.4f}")
        lines.append(f"{key:<14} | " + " | ".join(row_vals))

    lines.append(divider)
    return "\n".join(lines)


def format_cross_encoder_delta_table(summary: dict, k_values: list[int]) -> str:
    """Explicitly computes the Delta and Relative Lift of Cross-Encoder Reranking over Hybrid."""
    lines = []
    lines.append("\n=== CROSS-ENCODER CONTRIBUTION ANALYSIS (Reranked vs Hybrid) ===")
    header = f"{'Level':<12} | {'Metric':<10} | {'Hybrid':>10} | {'Reranked':>10} | {'Delta':>10} | {'Rel Lift':>10}"
    divider = "-" * len(header)
    lines.append(divider)
    lines.append(header)
    lines.append(divider)

    for level_key, level_name in [("chunk_level", "Chunk-level"), ("doc_level", "Doc-level")]:
        hybrid_m = summary[level_key]["Hybrid"]
        rerank_m = summary[level_key]["Reranked"]

        display_keys = ["MRR"] + [f"P@{k}" for k in k_values[:3]] + [f"R@{k}" for k in k_values[:3]] + [f"NDCG@{k}" for k in k_values[:3]] + [f"Hit@{k}" for k in k_values[:2]]

        for key in display_keys:
            h_val = hybrid_m.get(key, 0.0)
            r_val = rerank_m.get(key, 0.0)
            delta = r_val - h_val
            pct = ((delta / h_val) * 100) if h_val > 0 else 0.0
            sign = "+" if delta >= 0 else ""
            lines.append(f"{level_name:<12} | {key:<10} | {h_val:>10.4f} | {r_val:>10.4f} | {sign + f'{delta:.4f}':>10} | {sign + f'{pct:.2f}%':>10}")

        lines.append(divider)

    return "\n".join(lines)


def analyze_ranking_shifts(all_query_metrics: list[dict]) -> dict:
    """Counts how many queries were improved, degraded, or unaffected by cross-encoder reranking."""
    improved_mrr = 0
    degraded_mrr = 0
    tied_mrr = 0

    improved_p1 = 0
    degraded_p1 = 0
    tied_p1 = 0

    for m in all_query_metrics:
        h_mrr = m["methods"]["Hybrid"]["chunk_level"]["MRR"]
        r_mrr = m["methods"]["Reranked"]["chunk_level"]["MRR"]
        if r_mrr > h_mrr:
            improved_mrr += 1
        elif r_mrr < h_mrr:
            degraded_mrr += 1
        else:
            tied_mrr += 1

        h_hit1 = m["methods"]["Hybrid"]["chunk_level"]["Hit@1"]
        r_hit1 = m["methods"]["Reranked"]["chunk_level"]["Hit@1"]
        if r_hit1 > h_hit1:
            improved_p1 += 1
        elif r_hit1 < h_hit1:
            degraded_p1 += 1
        else:
            tied_p1 += 1

    total = len(all_query_metrics)
    return {
        "total_queries": total,
        "mrr_improved": improved_mrr,
        "mrr_degraded": degraded_mrr,
        "mrr_tied": tied_mrr,
        "p1_improved": improved_p1,
        "p1_degraded": degraded_p1,
        "p1_tied": tied_p1,
    }


def export_summary_csv(summary: dict, filepath: Path):
    """Exports the metric comparisons to a CSV file."""
    methods = ["BM25", "Vector", "Hybrid", "Reranked"]
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Level", "Metric"] + methods + ["Delta (Reranked-Hybrid)", "Rel_Lift_%"])

        for level_key, level_name in [("chunk_level", "Chunk-level"), ("doc_level", "Doc-level")]:
            metrics = summary[level_key]
            for metric in metrics["Hybrid"].keys():
                h_val = metrics["Hybrid"].get(metric, 0.0)
                r_val = metrics["Reranked"].get(metric, 0.0)
                delta = round(r_val - h_val, 4)
                rel_lift = round(((delta / h_val) * 100), 2) if h_val > 0 else 0.0
                row = [level_name, metric] + [metrics[m].get(metric, 0.0) for m in methods] + [delta, rel_lift]
                writer.writerow(row)

        # Latency row
        writer.writerow(["Runtime", "Latency_ms"] + [summary["latency_ms"][m] for m in methods] + ["-", "-"])


def find_hard_queries(all_query_metrics: list[dict], threshold_mrr: float = 0.5) -> list[dict]:
    """Identifies queries where Hybrid retrieval struggled (MRR < threshold)."""
    hard = []
    for item in all_query_metrics:
        hybrid_chunk_mrr = item["methods"]["Hybrid"]["chunk_level"]["MRR"]
        hybrid_doc_mrr = item["methods"]["Hybrid"]["doc_level"]["MRR"]
        if hybrid_chunk_mrr < threshold_mrr or hybrid_doc_mrr < threshold_mrr:
            hard.append({
                "question": item["question"],
                "source_doc_id": item["source_doc_id"],
                "hybrid_chunk_mrr": hybrid_chunk_mrr,
                "hybrid_doc_mrr": hybrid_doc_mrr,
                "vector_chunk_mrr": item["methods"]["Vector"]["chunk_level"]["MRR"],
                "bm25_chunk_mrr": item["methods"]["BM25"]["chunk_level"]["MRR"],
                "hybrid_retrieved_docs": item["methods"]["Hybrid"]["retrieved_doc_ids"]
            })
    return hard


def main():
    parser = argparse.ArgumentParser(description="Evaluate Information Retrieval (IR) metrics for RAG pipeline.")
    parser.add_argument("--sample", type=int, default=None, help="Sample size of queries to evaluate (default: all).")
    parser.add_argument("--k", type=str, default="1,3,5,10", help="Comma-separated K cutoffs (e.g. 1,3,5,10).")
    parser.add_argument("--dataset", type=str, default=str(EVAL_DATASET_PATH), help="Path to evaluation dataset JSON.")
    args = parser.parse_args()

    k_values = [int(k.strip()) for k in args.k.split(",") if k.strip().isdigit()]
    max_k = max(k_values) if k_values else 10

    dataset_path = Path(args.dataset)
    if not dataset_path.exists():
        print(f"Error: dataset file not found at {dataset_path}")
        sys.exit(1)

    with open(dataset_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Filter to answerable factual questions (evaluating retrieval requires ground-truth target)
    eval_queries = [
        item for item in data
        if item.get("expected_behavior") != "should_decline" and item.get("source_doc_id")
    ]

    if args.sample:
        eval_queries = eval_queries[:args.sample]
        print(f"Running on a sample of {len(eval_queries)} factual queries.")
    else:
        print(f"Loaded {len(eval_queries)} factual queries from {dataset_path}.")

    print("Initializing HybridRetriever and RerankingRetriever...")
    t0 = time.time()
    hybrid_retriever = HybridRetriever()
    reranker = RerankingRetriever()
    print(f"Retriever initialized in {time.time() - t0:.2f}s.\n")

    print(f"Evaluating {len(eval_queries)} queries across BM25, Vector, Hybrid, and Pipeline at K={k_values}...")
    query_eval_results = []
    start_eval = time.time()

    for idx, item in enumerate(eval_queries, start=1):
        q_text = item["question"]
        doc_id = item["source_doc_id"]
        res = evaluate_query(item, hybrid_retriever, reranker, k_values=k_values, max_k=max_k)
        query_eval_results.append(res)

        if idx % 10 == 0 or idx == len(eval_queries):
            elapsed = time.time() - start_eval
            rate = idx / elapsed
            print(f"  Processed {idx}/{len(eval_queries)} queries ({rate:.1f} queries/s)...")

    # Aggregate metrics
    summary = aggregate_metrics(query_eval_results, k_values)

    # Print tables
    chunk_table = format_table("CHUNK-LEVEL METRICS (Exact Passage Retrieval)", summary["chunk_level"], k_values)
    doc_table = format_table("DOCUMENT-LEVEL METRICS (Incident Document Retrieval)", summary["doc_level"], k_values)
    delta_table = format_cross_encoder_delta_table(summary, k_values)

    print(chunk_table)
    print(doc_table)
    print(delta_table)

    # Ranking shifts
    shifts = analyze_ranking_shifts(query_eval_results)
    print("\n=== CROSS-ENCODER RANKING SHIFT ANALYSIS ===")
    print(f"  Total queries: {shifts['total_queries']}")
    print(f"  Queries with MRR Improved by Reranker: {shifts['mrr_improved']} ({100 * shifts['mrr_improved'] / shifts['total_queries']:.1f}%)")
    print(f"  Queries with MRR Degraded by Reranker: {shifts['mrr_degraded']} ({100 * shifts['mrr_degraded'] / shifts['total_queries']:.1f}%)")
    print(f"  Queries with MRR Unchanged:           {shifts['mrr_tied']} ({100 * shifts['mrr_tied'] / shifts['total_queries']:.1f}%)")
    print(f"  Top-1 Hit (P@1) Improved:              {shifts['p1_improved']} ({100 * shifts['p1_improved'] / shifts['total_queries']:.1f}%)")
    print(f"  Top-1 Hit (P@1) Degraded:              {shifts['p1_degraded']} ({100 * shifts['p1_degraded'] / shifts['total_queries']:.1f}%)")

    print("\n=== AVERAGE RETRIEVAL LATENCY (per query) ===")
    for m, lat in summary["latency_ms"].items():
        print(f"  {m:<10}: {lat:>8.2f} ms")

    # Hard queries analysis
    hard_queries = find_hard_queries(query_eval_results, threshold_mrr=0.5)
    print(f"\n=== DIAGNOSTICS ===")
    print(f"Total queries evaluated: {len(query_eval_results)}")
    print(f"Queries with Hybrid Chunk MRR < 0.5: {len(hard_queries)} ({100 * len(hard_queries) / len(query_eval_results):.1f}%)")

    # Save summary JSON
    summary_json_path = RESULTS_DIR / "retrieval_metrics_summary.json"
    with open(summary_json_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"\nSaved metrics summary to {summary_json_path}")

    # Save summary CSV
    summary_csv_path = RESULTS_DIR / "retrieval_metrics_summary.csv"
    export_summary_csv(summary, summary_csv_path)
    print(f"Saved metrics CSV to {summary_csv_path}")

    # Save per-query diagnostics
    diag_path = RESULTS_DIR / "retrieval_query_diagnostics.json"
    with open(diag_path, "w", encoding="utf-8") as f:
        json.dump({
            "summary": summary,
            "hard_queries": hard_queries,
            "queries": query_eval_results
        }, f, indent=2)
    print(f"Saved per-query diagnostics to {diag_path}")


if __name__ == "__main__":
    main()

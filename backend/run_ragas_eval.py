"""
Phase 9: Evaluation using Ragas
------------------------------------
Runs the full pipeline (hybrid retrieval -> reranking -> LLM answer generation)
against every question in data/eval/eval_dataset.json, then scores the results.

Two separate evaluation paths, since the dataset has two question types:
  1. "should_answer" questions -> scored with real Ragas metrics (faithfulness,
     answer relevancy, context precision, context recall, answer correctness)
  2. "should_decline" questions -> Ragas has no built-in "did it correctly refuse"
     metric, so we use a simple custom keyword check instead

Install first:
    pip install ragas datasets langchain-groq langchain-huggingface
"""

import json
import time
from pathlib import Path

from datasets import Dataset
from ragas import evaluate
from ragas.run_config import RunConfig
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
    context_precision,
    context_recall,
    answer_correctness,
)
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper
from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings

from reranking import RerankingRetriever
from generate_answer import build_context_block, SYSTEM_PROMPT
from llm_config import llm as project_llm, GROQ_API_KEY

EVAL_DATASET_PATH = Path("data/eval/eval_dataset.json")
RESULTS_DIR = Path("data/eval")

# Groq tracks token-per-day limits SEPARATELY per model. Using a different,
# smaller model for the Ragas judge than your main pipeline (llama-3.3-70b)
# means judging draws from its own separate quota, instead of competing with
# your pipeline's own calls for the same 100k/day budget.
RAGAS_JUDGE_MODEL = "llama-3.1-8b-instant"

# Caps how many questions go through the MAIN pipeline (run_pipeline) in this
# run -- separate from EVAL_SAMPLE_SIZE below, which only limits the Ragas
# metrics step. Useful for a cheap end-to-end smoke test. Set to None to run
# the full eval_dataset.json.
EVAL_DATASET_SAMPLE = None

# Optional: cap how many factual questions to send through Ragas in one run,
# in case your daily quota is still tight. Set to None to run everything.
EVAL_SAMPLE_SIZE = None

# If the main pipeline hits a rate limit, wait this long before retrying once,
# rather than crashing the whole eval run over one question.
RATE_LIMIT_RETRY_WAIT_SECONDS = 300

# Phrases that indicate the model appropriately declined to answer -- used only
# for the "should_decline" questions, to check the refusal actually happened.
DECLINE_INDICATORS = [
    "do not have", "doesn't have", "does not contain", "not contain",
    "cannot answer", "can't answer", "no information", "not covered",
    "not provided", "insufficient information", "context does not",
    "unable to answer", "not mentioned", "not available in the",
]


def run_pipeline(query: str, retriever: RerankingRetriever) -> dict:
    """
    Runs one question through the full pipeline and returns everything Ragas
    needs: the generated answer, and the raw context strings actually used.
    Retries once with a wait if the main model hits a Groq rate limit, instead
    of letting one question's failure crash the entire eval run.
    """
    chunks = retriever.retrieve_and_rerank(query)
    contexts = [c["payload"]["text"] for c in chunks]

    if not chunks:
        return {"answer": "No relevant context found.", "contexts": []}

    context_block = build_context_block(chunks)
    prompt = f"""{SYSTEM_PROMPT}

Context:
{context_block}

Question: {query}

Answer (remember to cite sources using [1], [2], etc.):"""

    try:
        response = project_llm.complete(prompt)
        return {"answer": response.text.strip(), "contexts": contexts}
    except Exception as e:
        if "rate_limit" in str(e).lower() or "429" in str(e):
            print(f"  Rate limit hit, waiting {RATE_LIMIT_RETRY_WAIT_SECONDS}s before retrying once...")
            time.sleep(RATE_LIMIT_RETRY_WAIT_SECONDS)
            try:
                response = project_llm.complete(prompt)
                return {"answer": response.text.strip(), "contexts": contexts}
            except Exception as e2:
                print(f"  Retry also failed: {e2}")
                return {"answer": "[SKIPPED -- rate limit exceeded after retry]", "contexts": contexts}
        else:
            print(f"  Unexpected error: {e}")
            return {"answer": f"[SKIPPED -- error: {e}]", "contexts": contexts}


def evaluate_factual_questions(rows: list[dict]) -> None:
    """Runs Ragas metrics on the 'should_answer' subset."""
    if not rows:
        print("No factual (should_answer) questions to evaluate.")
        return

    dataset_dict = {
        "question": [r["question"] for r in rows],
        "answer": [r["answer"] for r in rows],
        "contexts": [r["contexts"] for r in rows],
        "ground_truth": [r["ground_truth_answer"] for r in rows],
    }

    if EVAL_SAMPLE_SIZE:
        dataset_dict = {k: v[:EVAL_SAMPLE_SIZE] for k, v in dataset_dict.items()}
        print(f"(Limited to a sample of {EVAL_SAMPLE_SIZE} questions for this run)")

    dataset = Dataset.from_dict(dataset_dict)

    # Ragas defaults to OpenAI -- point it at Groq + a local HuggingFace embedding
    # model instead, so the whole eval runs on your existing free-tier setup.
    # Using a SEPARATE model (RAGAS_JUDGE_MODEL) from your main pipeline's model
    # means this draws from its own daily token quota on Groq, not competing
    # with the calls your pipeline itself already made.
    ragas_llm = LangchainLLMWrapper(ChatGroq(
        model=RAGAS_JUDGE_MODEL, api_key=GROQ_API_KEY, temperature=0.0
    ))
    ragas_embeddings = LangchainEmbeddingsWrapper(
        HuggingFaceEmbeddings(model_name="BAAI/bge-m3")
    )

    # Retry with backoff on rate limits / timeouts instead of failing straight to NaN.
    # max_wait is in seconds -- Groq's error messages showed waits up to ~40 minutes
    # in the worst case, but most retries should be much shorter than that.
    run_config = RunConfig(timeout=300, max_retries=15, max_wait=120)

    print(f"\nRunning Ragas metrics on {len(dataset_dict['question'])} factual questions "
          f"(judge model: {RAGAS_JUDGE_MODEL})...")
    results = evaluate(
        dataset,
        metrics=[faithfulness, answer_relevancy, context_precision, context_recall, answer_correctness],
        llm=ragas_llm,
        embeddings=ragas_embeddings,
        run_config=run_config,
    )

    print("\n=== Ragas Metrics (factual questions) ===")
    print(results)

    results_df = results.to_pandas()
    out_path = RESULTS_DIR / "ragas_results.csv"
    results_df.to_csv(out_path, index=False)
    print(f"\nPer-question results saved to {out_path}")


def evaluate_decline_questions(rows: list[dict]) -> None:
    """Custom check for the 'should_decline' subset -- did the model appropriately refuse?"""
    if not rows:
        print("No unanswerable (should_decline) questions to evaluate.")
        return

    print(f"\n=== Refusal check (should_decline questions) ===")
    correct_refusals = 0

    for r in rows:
        answer_lower = r["answer"].lower()
        declined = any(phrase in answer_lower for phrase in DECLINE_INDICATORS)
        status = "CORRECTLY DECLINED" if declined else "FAILED -- answered anyway"
        if declined:
            correct_refusals += 1

        print(f"\nQ: {r['question']}")
        print(f"  Status: {status}")
        print(f"  Answer: {r['answer'][:150]}...")

    print(f"\nRefusal accuracy: {correct_refusals}/{len(rows)} "
          f"({100 * correct_refusals / len(rows):.0f}%)")


def main():
    with open(EVAL_DATASET_PATH, "r", encoding="utf-8") as f:
        eval_dataset = json.load(f)

    if EVAL_DATASET_SAMPLE:
        eval_dataset = eval_dataset[:EVAL_DATASET_SAMPLE]
        print(f"(Limited to a sample of {EVAL_DATASET_SAMPLE} questions for the main pipeline this run)")

    print(f"Loaded {len(eval_dataset)} eval questions.")

    retriever = RerankingRetriever()

    factual_rows = []
    decline_rows = []

    for item in eval_dataset:
        print(f"\nRunning: {item['question']}")
        result = run_pipeline(item["question"], retriever)

        row = {
            "question": item["question"],
            "answer": result["answer"],
            "contexts": result["contexts"],
        }

        if item.get("expected_behavior") == "should_decline":
            decline_rows.append(row)
        else:
            row["ground_truth_answer"] = item.get("ground_truth_answer", "")
            factual_rows.append(row)

    evaluate_factual_questions(factual_rows)
    evaluate_decline_questions(decline_rows)


if __name__ == "__main__":
    main()
"""
Phase 9 (prep step, part 2): Build the final eval dataset
------------------------------------------------------------
Combines your manually-reviewed factual Q&A pairs (data/eval/eval_candidates.json,
filtered to only entries you marked "reviewed": true) with a small set of
deliberately UNANSWERABLE questions -- things not covered anywhere in your
20-document corpus. These test whether your pipeline correctly admits it doesn't
know, instead of hallucinating a plausible-sounding but made-up answer (Rule 2
from your Phase 8 system prompt).

Output: data/eval/eval_dataset.json -> the final dataset used by the Ragas
evaluation script.
"""

import json
from pathlib import Path

EVAL_DIR = Path("data/eval")

# Edit/expand this list as you like -- these should be things genuinely NOT covered
# by any of your 20 scraped Cloudflare postmortems. A good unanswerable question is
# plausible-sounding (so a weak pipeline might be tempted to guess) but verifiably
# absent from your corpus.
UNANSWERABLE_QUESTIONS = [
    {
        "question": "How many employees does Cloudflare have?",
        "expected_behavior": "should_decline",
        "note": "Not covered by any incident postmortem in the corpus.",
    },
    {
        "question": "What caused Cloudflare's July 2019 global outage?",
        "expected_behavior": "should_decline",
        "note": "A real historical Cloudflare incident, but not one of the 20 scraped documents -- tests whether the model answers from outside training knowledge instead of the provided corpus.",
    },
    {
        "question": "Who is Cloudflare's current Chief Financial Officer?",
        "expected_behavior": "should_decline",
        "note": "Company leadership info, not covered by incident postmortems.",
    },
    {
        "question": "What was the stock price impact of the February 20, 2026 outage?",
        "expected_behavior": "should_decline",
        "note": "Financial market data not covered in the technical postmortem.",
    },
    {
        "question": "How does Cloudflare's pricing compare to AWS CloudFront?",
        "expected_behavior": "should_decline",
        "note": "Competitive/pricing question, not covered by incident postmortems.",
    },
]


def main():
    candidates_path = EVAL_DIR / "eval_candidates.json"
    if not candidates_path.exists():
        raise FileNotFoundError(f"Expected {candidates_path} -- run generate_eval_candidates.py first.")

    with open(candidates_path, "r", encoding="utf-8") as f:
        candidates = json.load(f)

    reviewed = [c for c in candidates if c.get("reviewed") is True]
    skipped = len(candidates) - len(reviewed)

    print(f"Loaded {len(candidates)} candidates -- {len(reviewed)} marked reviewed, {skipped} not included.")

    # Tag the reviewed factual questions with expected_behavior too, for consistency
    # with the unanswerable ones -- makes the eval script's logic simpler later.
    for r in reviewed:
        r["expected_behavior"] = "should_answer"

    final_dataset = reviewed + UNANSWERABLE_QUESTIONS

    out_path = EVAL_DIR / "eval_dataset.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(final_dataset, f, indent=2)

    print(f"Added {len(UNANSWERABLE_QUESTIONS)} unanswerable test questions.")
    print(f"\nFinal eval dataset: {len(final_dataset)} total questions saved to {out_path}")
    print(f"  - {len(reviewed)} factual questions (should_answer)")
    print(f"  - {len(UNANSWERABLE_QUESTIONS)} unanswerable questions (should_decline)")


if __name__ == "__main__":
    main()
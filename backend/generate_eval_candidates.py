"""
Phase 9 (prep step): Generate candidate evaluation Q&A pairs
------------------------------------------------------------------
For each raw document (data/raw/*.md), asks the LLM to draft 3 question/answer
pairs based ONLY on that document's content -- preferring questions with
specific, checkable facts (numbers, dates, names) over vague ones, since those
are the most useful for testing whether your RAG pipeline preserves precision.

IMPORTANT: these are CANDIDATES, not final ground truth. You must review each
one against the source article and fix/discard any that are wrong, ambiguous,
or too easy for an LLM to answer without needing the source at all. Treating
unreviewed LLM-generated answers as ground truth would mean testing your
pipeline against its own family's guesses, not real correctness.

Output: data/eval/eval_candidates.json -> for you to review and trim down
"""

import json
import re
from pathlib import Path

from llm_config import llm

RAW_DIR = Path("data/raw")
EVAL_DIR = Path("data/eval")
EVAL_DIR.mkdir(parents=True, exist_ok=True)

QUESTIONS_PER_DOC = 3

GENERATION_PROMPT_TEMPLATE = """You are creating evaluation questions for a RAG system \
that answers questions about this Cloudflare incident postmortem article.

Based ONLY on the article text below, write exactly {n} question/answer pairs that:
- Have a specific, factual, checkable answer (prefer exact numbers, dates, durations, \
names, or root causes over vague/opinion-based questions)
- Could realistically be asked by someone trying to understand this incident
- Have an answer that is directly stated or clearly derivable from the article text

Respond ONLY in this exact JSON format, nothing else, no markdown code fences:
[
  {{"question": "...", "ground_truth_answer": "..."}},
  {{"question": "...", "ground_truth_answer": "..."}}
]

Article title: {title}

Article text:
{text}
"""


def parse_front_matter(raw_text: str):
    match = re.match(r"^---\n(.*?)\n---\n\n(.*)$", raw_text, re.DOTALL)
    if not match:
        return {}, raw_text
    front_matter_raw, body = match.groups()
    metadata = {}
    for line in front_matter_raw.split("\n"):
        if ":" in line:
            key, _, value = line.partition(":")
            metadata[key.strip()] = value.strip()
    return metadata, body


def extract_json_array(text: str) -> list[dict]:
    """
    LLMs sometimes wrap JSON in markdown code fences or add stray text despite
    instructions not to. This pulls out just the [...] array portion defensively.
    """
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        return []
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return []


def main():
    manifest_path = RAW_DIR / "manifest.json"
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    all_candidates = []

    for entry in manifest:
        md_path = Path(entry["file"])
        if not md_path.exists():
            print(f"  Skipping missing file: {md_path}")
            continue

        with open(md_path, "r", encoding="utf-8") as f:
            raw_text = f.read()

        front_matter, body = parse_front_matter(raw_text)
        title = front_matter.get("title") or entry.get("title") or entry["slug"]

        # Cap article length sent to the LLM to keep prompts reasonably sized --
        # 6000 chars comfortably covers even your longer postmortems
        truncated_body = body[:6000]

        prompt = GENERATION_PROMPT_TEMPLATE.format(
            n=QUESTIONS_PER_DOC, title=title, text=truncated_body
        )

        print(f"Generating questions for: {title}")
        response = llm.complete(prompt)
        qa_pairs = extract_json_array(response.text)

        if not qa_pairs:
            print(f"  WARNING: could not parse questions for {entry['slug']}, skipping.")
            continue

        for qa in qa_pairs:
            all_candidates.append({
                "question": qa.get("question", ""),
                "ground_truth_answer": qa.get("ground_truth_answer", ""),
                "source_doc_id": entry["slug"],
                "source_title": title,
                "source_url": entry.get("url", ""),
                "reviewed": False,  # you'll flip this to true as you review each one
            })

        print(f"  Got {len(qa_pairs)} candidate questions.")

    out_path = EVAL_DIR / "eval_candidates.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_candidates, f, indent=2)

    print(f"\nDone. {len(all_candidates)} candidate Q&A pairs saved to {out_path}")
    print("Next: open this file and review each one against the source article --")
    print("fix wrong answers, discard bad questions, then save as eval_dataset.json")


if __name__ == "__main__":
    main()
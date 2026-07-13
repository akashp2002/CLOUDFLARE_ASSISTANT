"""
Phase 8: LLM answer generation with citations
--------------------------------------------------
Takes the top reranked chunks (Phase 7) for a given query, builds a prompt that
instructs the LLM to answer ONLY using those chunks (not its own general
knowledge), and requires it to cite which chunk(s) support each claim.

Uses Groq (llm_config.py) as the LLM backend.

Install first (if not already):
    pip install llama-index-llms-groq
"""

from reranking import RerankingRetriever
from llm_config import llm  # pre-configured Groq LLM (see llm_config.py)
from langsmith import traceable

SYSTEM_PROMPT = """You are a technical assistant answering questions about Cloudflare \
incident postmortems. You must follow these rules strictly:

1. Answer ONLY using the information in the provided context chunks below. \
Do not use any outside knowledge, even if you know the answer from elsewhere.
2. If the context does not contain enough information to answer the question, \
say so explicitly instead of guessing.
3. Every factual claim in your answer must be followed by a citation marker \
like [1], [2], etc., referring to the numbered context chunk that supports it.
4. Be concise and precise. Prefer exact figures and quotes from the context \
over vague paraphrasing when the context contains specific numbers or facts.
"""


def build_context_block(chunks: list[dict]) -> str:
    """
    Formats the reranked chunks into a numbered context block for the prompt,
    e.g.:
        [1] (Route leak incident on January 22, 2026 - What happened: the configuration error)
        On January 22, 2026, at 20:25 UTC, we pushed a change...

    The numbering here is what the LLM's citation markers ([1], [2]...) will refer to.
    """
    blocks = []
    for i, chunk in enumerate(chunks, 1):
        payload = chunk["payload"]
        header = f"[{i}] ({payload.get('title', '')} - {payload.get('section_heading', 'Introduction')})"
        blocks.append(f"{header}\n{payload['text']}")
    return "\n\n".join(blocks)


def build_citation_map(chunks: list[dict]) -> dict:
    """
    Maps citation number -> source metadata, so we can print a clean "Sources"
    list after the answer, translating [1], [2] back into real titles/URLs.
    """
    citation_map = {}
    for i, chunk in enumerate(chunks, 1):
        payload = chunk["payload"]
        citation_map[i] = {
            "title": payload.get("title", ""),
            "section": payload.get("section_heading", "") or "Introduction",
            "url": payload.get("source_url", ""),
        }
    return citation_map


@traceable(name="answer_question", run_type="chain")
def answer_question(query: str, retriever: RerankingRetriever) -> dict:
    chunks = retriever.retrieve_and_rerank(query)

    if not chunks:
        print("No relevant chunks found for this question.")
        return {"answer": None, "citations": {}}

    context_block = build_context_block(chunks)
    citation_map = build_citation_map(chunks)

    prompt = f"""{SYSTEM_PROMPT}

Context:
{context_block}

Question: {query}

Answer (remember to cite sources using [1], [2], etc.):"""

    response = llm.complete(prompt)
    answer_text = response.text.strip()

    print("=" * 60)
    print("ANSWER")
    print("=" * 60)
    print(answer_text)

    print("\n" + "=" * 60)
    print("SOURCES")
    print("=" * 60)
    for num, source in citation_map.items():
        print(f"[{num}] {source['title']} - {source['section']}")
        print(f"    {source['url']}")

    # Returned (rather than just printed) so LangSmith captures a real output
    # for this trace, not None -- makes traces actually useful to inspect later.
    return {"answer": answer_text, "citations": citation_map}


if __name__ == "__main__":
    retriever = RerankingRetriever()

    test_query = "How many Gbps of traffic were discarded during the Miami route leak?"
    print(f"\nQuery: {test_query}\n")

    answer_question(test_query, retriever)
"""
FastAPI backend for the RAG pipeline.
----------------------------------------
Wraps the existing retrieval + reranking + generation pipeline (Phases 6-8)
in a simple HTTP API, so a React frontend (or anything else) can query it
over the network instead of running Python scripts directly.

The heavy models (BGE-M3, reranker, BM25 index, Qdrant connection) are loaded
ONCE at server startup, not per-request -- this matters a lot for response
time, since reloading a ~2GB embedding model on every request would be very slow.

Install first:
    pip install fastapi uvicorn[standard]

Run with:
    uvicorn app:app --reload --port 8000
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from reranking import RerankingRetriever
from generate_answer import build_context_block, build_citation_map, SYSTEM_PROMPT
from llm_config import llm

# A simple in-memory holder for the retriever, so it's loaded once and reused
# across every request instead of being rebuilt each time.
retriever_holder: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Runs once when the server starts up -- loads all the heavy models/connections.
    print("Loading RAG pipeline (this takes a moment on first startup)...")
    retriever_holder["retriever"] = RerankingRetriever()
    print("RAG pipeline ready. API is now serving requests.")
    yield
    # (nothing needed on shutdown for this project)


app = FastAPI(title="Cloudflare Incident RAG API", lifespan=lifespan)

# Allows your React dev server (typically localhost:5173 for Vite, or
# localhost:3000 for Create React App) to call this API from the browser.
# In production, restrict allow_origins to your actual frontend's domain.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174", "http://localhost:3000","http://localhost:8081","http://localhost:8080"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class QueryRequest(BaseModel):
    question: str


class Citation(BaseModel):
    number: int
    title: str
    section: str
    url: str


class QueryResponse(BaseModel):
    answer: str
    citations: list[Citation]


@app.get("/health")
def health_check():
    """Simple endpoint to confirm the server is up and the pipeline loaded correctly."""
    return {"status": "ok", "pipeline_loaded": "retriever" in retriever_holder}


@app.post("/query", response_model=QueryResponse)
def query(request: QueryRequest):
    if not request.question or not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    retriever = retriever_holder["retriever"]
    chunks = retriever.retrieve_and_rerank(request.question)

    if not chunks:
        return QueryResponse(answer="No relevant information found for this question.", citations=[])

    context_block = build_context_block(chunks)
    citation_map = build_citation_map(chunks)

    prompt = f"""{SYSTEM_PROMPT}

Context:
{context_block}

Question: {request.question}

Answer (remember to cite sources using [1], [2], etc.):"""

    response = llm.complete(prompt)
    answer_text = response.text.strip()

    citations = [
        Citation(number=num, title=source["title"], section=source["section"], url=source["url"])
        for num, source in citation_map.items()
    ]

    return QueryResponse(answer=answer_text, citations=citations)
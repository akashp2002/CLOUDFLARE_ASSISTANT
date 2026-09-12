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
import asyncio
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import json

from reranking import RerankingRetriever
from generate_answer import build_context_block, build_citation_map, SYSTEM_PROMPT
from llm_config import llm

# A simple in-memory holder for the retriever, so it's loaded once and reused
# across every request instead of being rebuilt each time.
retriever_holder: dict = {}


# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     # Runs once when the server starts up -- loads all the heavy models/connections.
#     print("Loading RAG pipeline (this takes a moment on first startup)...")
#     retriever_holder["retriever"] = RerankingRetriever()
#     print("RAG pipeline ready. API is now serving requests.")
#     yield
#     # (nothing needed on shutdown for this project)
retriever_holder = {
    "retriever": None
}


app = FastAPI(title="Cloudflare Incident RAG API")

# Allows your React dev server (typically localhost:5173 for Vite, or
# localhost:3000 for Create React App) to call this API from the browser.
# In production, restrict allow_origins to your actual frontend's domain.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173","https://cloudflare-assistant.vercel.app", "http://localhost:5174", "http://localhost:3000","http://localhost:8081","http://localhost:8080"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class QueryRequest(BaseModel):
    question: str
    history: list["HistoryMessage"] = []


class HistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


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


@app.post("/query")
def query(request: QueryRequest):
    if not request.question or not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    async def event_stream():
        yield f"data: {json.dumps({'type': 'status', 'text': 'Searching the knowledge base...'})}\n\n"

        if retriever_holder["retriever"] is None:
            print("Loading RAG pipeline...")
            retriever_holder["retriever"] = await asyncio.to_thread(RerankingRetriever)

        retriever = retriever_holder["retriever"]
        recent_user_questions = [
            message.content
            for message in request.history[-6:]
            if message.role == "user"
        ]
        retrieval_query = "\n".join([*recent_user_questions, request.question])
        chunks = await asyncio.to_thread(
            retriever.retrieve_and_rerank,
            retrieval_query,
        )

        if not chunks:
            yield f"data: {json.dumps({'type': 'content', 'text': 'No relevant information found for this question.'})}\n\n"
            yield f"data: {json.dumps({'type': 'citations', 'citations': []})}\n\n"
            return

        context_block = build_context_block(chunks)
        citation_map = build_citation_map(chunks)

        history_block = "\n".join(
            f"{message.role.title()}: {message.content}"
            for message in request.history[-6:]
        )
        conversation_context = (
            f"Conversation history:\n{history_block}\n\n"
            if history_block
            else ""
        )

        prompt = f"""{SYSTEM_PROMPT}

Context:
{context_block}

{conversation_context}Question: {request.question}

Answer (remember to cite sources using [1], [2], etc.):"""

        citations = [
            {"number": num, "title": source["title"], "section": source["section"], "url": source["url"]}
            for num, source in citation_map.items()
        ]

        response_gen = await llm.astream_complete(prompt)
        async for chunk in response_gen:
            if chunk.delta:
                yield f"data: {json.dumps({'type': 'content', 'text': chunk.delta})}\n\n"
        
        yield f"data: {json.dumps({'type': 'citations', 'citations': citations})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
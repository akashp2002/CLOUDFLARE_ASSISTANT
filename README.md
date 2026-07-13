# Cloudflare Incident RAG

A full-stack Retrieval-Augmented Generation (RAG) system for answering questions about Cloudflare's public incident postmortems, built end-to-end as a portfolio project.

Ask a question like *"How long did the January 2026 route leak incident last?"* and get a grounded, cited answer sourced directly from the original blog posts — with the system explicitly declining to answer when the corpus doesn't contain the information, rather than guessing.

## Architecture

```
User (React frontend)
        |
        v
   FastAPI backend
        |
        v
  Hybrid Retrieval  <-- Vector search (Qdrant + BGE-M3) + BM25 keyword search
        |                fused via Reciprocal Rank Fusion (RRF)
        v
  Cross-Encoder Reranking  <-- BAAI/bge-reranker-v2-m3, re-scores top candidates
        |
        v
  LLM Answer Generation  <-- Groq (Llama 3.3), strict citation-only prompting
        |
        v
  Answer + Sources returned to the user
```

## Pipeline phases

| Phase | What it does |
|---|---|
| 1. Project setup | FastAPI backend, React frontend, Docker Compose orchestration |
| 2. Data ingestion | Scrapes 20 Cloudflare incident postmortems via `trafilatura`, saves as markdown with YAML front matter |
| 3. Recursive chunking | Splits documents by heading structure first, then by paragraph if a section is still oversized, with metadata (title, URL, section heading) attached to every chunk |
| 4. Embedding generation | BGE-M3 dense embeddings (1024-dim) for every chunk |
| 5. Vector storage | Chunks + embeddings stored in Qdrant with cosine similarity |
| 6. Hybrid retrieval | Combines vector search and BM25 keyword search via Reciprocal Rank Fusion, so precise figures/numbers aren't lost to embedding compression |
| 7. Reranking | Cross-encoder (`bge-reranker-v2-m3`) re-scores the top candidates by reading the query and each chunk together, correcting ordering mistakes from the faster retrieval stage |
| 8. Answer generation | Groq-hosted Llama 3.3, prompted to answer only from retrieved context, cite every claim, and explicitly decline when context is insufficient |
| 9. Evaluation | Ragas metrics (faithfulness, answer relevancy, context precision/recall, answer correctness) against a manually-reviewed eval set, plus a custom refusal-accuracy check on deliberately unanswerable questions |
| 10. Tracing | LangSmith traces every pipeline stage per-request for debugging |
| 11. Deployment | Dockerized backend (FastAPI, CPU inference) + frontend (React, served via nginx) + Qdrant, orchestrated with Docker Compose |

## Tech stack

- **Backend:** FastAPI, Python
- **Frontend:** React (Vite)
- **Vector DB:** Qdrant
- **Embeddings:** BAAI/bge-m3
- **Reranker:** BAAI/bge-reranker-v2-m3
- **LLM:** Groq (Llama 3.3 70B)
- **Evaluation:** Ragas
- **Tracing:** LangSmith
- **Orchestration:** Docker Compose

## Running with Docker (recommended)

1. Clone the repo
2. Copy `backend/.env.example` to `backend/.env` and fill in your API keys (Groq, LangSmith)
3. Make sure `backend/data/` contains the pipeline outputs (`chunks/`, `embeddings/`) — see "Regenerating the pipeline" below if starting from scratch
4. From the project root:
   ```bash
   docker compose up --build
   ```
5. Once all three containers are up:
   - Frontend: http://localhost:3000
   - Backend API docs: http://localhost:8000/docs
   - Qdrant dashboard: http://localhost:6333/dashboard

## Regenerating the pipeline from scratch

If you don't have `backend/data/` populated yet, run these in order from inside `backend/` (with a Python virtual environment activated and Qdrant running):

```bash
python ingest_cloudflare_incidents.py
python fix_markdown_headings.py
python chunk_documents_llamaindex.py
python generate_embeddings.py
python upload_to_qdrant.py
```

Then either run `uvicorn app:app --reload --port 8000` directly, or rebuild the Docker image so it picks up the new `data/` folder.

## Running for local development (without Docker)

**Backend:**
```bash
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1   # Windows; use source venv/bin/activate on Mac/Linux
pip install -r ../requirements.txt
uvicorn app:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

**Qdrant:**
```bash
docker run -d --name qdrant-rag -p 6333:6333 -p 6334:6334 -v "${PWD}/qdrant_storage:/qdrant/storage" qdrant/qdrant
```

## Evaluation results

Evaluated against a 27-question manually-reviewed factual eval set plus 5 deliberately unanswerable questions, using Ragas.

**Refusal accuracy (unanswerable questions):** 5/5 (100%) — the system correctly declined to answer every out-of-scope question rather than hallucinating.

**Ragas metrics (factual questions):**

| Metric | Score |
|---|---|
| Faithfulness | _pending final run_ |
| Answer Relevancy | _pending final run_ |
| Context Precision | _pending final run_ |
| Context Recall | _pending final run_ |
| Answer Correctness | _pending final run_ |

_Full per-question results available in `backend/data/eval/ragas_results.csv`._

## Key design decisions

- **Hybrid retrieval over pure vector search:** Dense embeddings compress entire chunks into a single vector, which can blur precise figures (exact numbers, dates, IDs). BM25 keyword search acts as a safety net for exact-term matches, fused with vector results via Reciprocal Rank Fusion.
- **Reranking as a correction step:** Retrieval alone sometimes ranks the most relevant chunk below less-relevant ones (verified empirically during development — see project notes). A cross-encoder reranker, which reads the query and chunk together rather than comparing precomputed vectors, corrects this.
- **Explicit refusal over confident guessing:** The generation prompt is designed to make the LLM say "I don't know" when context is insufficient, rather than blending in outside knowledge — verified with a dedicated set of unanswerable test questions.
- **CPU inference in the deployed container:** Development used GPU acceleration; the deployed Docker image runs on CPU for portability, since GPU passthrough in Docker adds significant setup complexity that isn't worth it for a portfolio deployment.
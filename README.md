# CodeLens — GitHub Codebase Q&A

> Ask natural language questions about any GitHub repository. Powered by AST-aware chunking, hybrid retrieval, and LangGraph orchestration.

---

## What It Does

Paste a GitHub repo URL → CodeLens ingests the entire codebase using tree-sitter AST parsing → ask any question → get an answer with exact file paths, function names, and line numbers cited.

**Live demo:** [your-app.vercel.app](https://your-app.vercel.app)

---

## Architecture

```
User Question
      │
      ▼
┌─────────────────────────────────────────────────────┐
│                  LangGraph Pipeline                  │
│                                                      │
│  embed_query → hybrid_retrieve → rerank → generate  │
│                                                      │
│  1. Embed       Gemini embedding-001 (768 dims)      │
│  2. Retrieve    pgvector (cosine) + BM25, merged     │
│                 with Reciprocal Rank Fusion           │
│  3. Rerank      FlashRank cross-encoder (local)      │
│  4. Generate    Groq llama-3.3-70b, streamed via SSE │
└─────────────────────────────────────────────────────┘
      │
      ▼
  Streamed answer + cited sources (file, function, lines)


Ingestion Pipeline (one-time per repo, incremental after)

GitHub Repo URL
      │
      ▼
PyGitHub → fetch files → tree-sitter AST parse
      │
      ▼
Chunk at function/class boundaries (not naive text split)
      │
      ▼
Gemini embeddings (768 dims, batched, rate-limit safe)
      │
      ▼
Supabase pgvector (HNSW index) + BM25 index (in-memory)
```

---

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| Backend framework | FastAPI | Async-native, streaming support via SSE |
| Orchestration | LangGraph | Stateful multi-node pipeline, clean separation of concerns |
| Code parsing | tree-sitter | AST-based chunking — splits at function/class boundaries, not arbitrary character counts |
| Embeddings | Gemini embedding-001 | 768-dim output (within pgvector HNSW limit), code-aware |
| Vector store | Supabase pgvector | Managed PostgreSQL + HNSW index, production-ready |
| Keyword search | BM25 (rank-bm25) | Exact symbol/function name lookups that semantic search misses |
| Result fusion | Reciprocal Rank Fusion | Merges vector + BM25 ranked lists without score normalization |
| Reranking | FlashRank (local) | Cross-encoder accuracy without API cost or latency |
| LLM | Groq llama-3.3-70b | 1000 RPD free tier, fast inference |
| Streaming | SSE (Server-Sent Events) | Token-by-token streaming to frontend |
| Frontend | React + Vite | Fast build, component-based |
| Backend deploy | Render (Docker) | Free tier, Docker deployment |
| Frontend deploy | Vercel | Zero-config, instant CDN |

---

## Key Engineering Decisions

**AST chunking over naive text splitting**
tree-sitter parses code into an AST and extracts function/class definition nodes. Each chunk is one complete, semantically meaningful unit with metadata: file path, function name, class name, language, start/end line. Naive splitting (e.g. every 500 chars) cuts through function bodies and destroys context.

**Hybrid retrieval (dense + sparse)**
Dense vector search handles conceptual questions ("how does auth work?"). BM25 handles exact symbol lookups ("where is `jwt.decode` called?"). Neither alone is sufficient — running both and merging with RRF gives the best of both.

**Two-stage retrieval**
Retrieve top 20 candidates cheaply (vector + BM25), then rerank to top 5 with a cross-encoder (FlashRank). Cross-encoders are too slow to run on the full corpus but very accurate on a small candidate set.

**Incremental ingestion**
Every repo stores its latest commit SHA. On re-ingest, we compare SHAs, fetch only the diff, and process only added/modified/removed files. Renamed files are split into a remove + add operation.

**SSE streaming over WebSockets**
The query pipeline takes 5–10 seconds end-to-end. SSE lets us push status events (embedding, searching, reranking) and LLM tokens to the frontend as they happen. SSE is simpler than WebSockets for this one-directional use case and works over plain HTTP.

---

## Local Setup

**Backend**
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Fill in: GROQ_API_KEY, GOOGLE_API_KEY, GITHUB_TOKEN, SUPABASE_URL, SUPABASE_SERVICE_KEY

uvicorn app.main:app --reload
```

**Frontend**
```bash
cd frontend
npm install
# Create .env with: VITE_API_URL=http://localhost:8000
npm run dev
```

**Supabase setup**
```sql
-- Enable pgvector
create extension if not exists vector;

-- Repos table
create table repos (
  id uuid primary key default gen_random_uuid(),
  repo_url text unique not null,
  repo_name text not null,
  last_commit_sha text,
  last_ingested_at timestamptz default now(),
  status text default 'active'
);

-- Chunks table
create table chunks (
  id uuid primary key default gen_random_uuid(),
  repo_id uuid references repos(id) on delete cascade,
  file_path text,
  name text,
  class_name text,
  node_type text,
  language text,
  start_line int,
  end_line int,
  content text,
  embedding vector(768)
);

-- HNSW index for fast cosine similarity search
create index on chunks using hnsw (embedding vector_cosine_ops);

-- match_chunks function used by similarity search
create or replace function match_chunks(
  query_embedding vector(768),
  match_repo_id uuid,
  match_count int
)
returns table (
  id uuid, repo_id uuid, file_path text, name text,
  class_name text, node_type text, language text,
  start_line int, end_line int, content text,
  similarity float
)
language sql stable as $$
  select
    id, repo_id, file_path, name, class_name, node_type,
    language, start_line, end_line, content,
    1 - (embedding <=> query_embedding) as similarity
  from chunks
  where repo_id = match_repo_id
  order by embedding <=> query_embedding
  limit match_count;
$$;
```

---

## Project Structure

```
github-codebase-qa/
├── backend/
│   ├── app/
│   │   ├── api/routes.py          # POST /ingest, POST /query
│   │   ├── core/
│   │   │   ├── config.py          # Pydantic settings
│   │   │   ├── ingestion/
│   │   │   │   ├── pipeline.py    # Full + incremental ingestion
│   │   │   │   ├── github_loader.py   # PyGitHub fetcher
│   │   │   │   ├── code_chunker.py    # tree-sitter AST chunker
│   │   │   │   └── embedder.py    # Gemini embeddings, batched
│   │   ├── db/vector_store.py     # Supabase async client
│   │   ├── graph/
│   │   │   ├── state.py           # LangGraph TypedDict state
│   │   │   ├── nodes.py           # embed → retrieve → rerank → generate
│   │   │   └── workflow.py        # StateGraph wiring
│   │   ├── schemas/               # Pydantic request/response models
│   │   ├── services/query_service.py  # SSE streaming orchestrator
│   │   └── main.py
│   ├── Dockerfile
│   └── requirements.txt
└── frontend/
    ├── src/
    │   ├── components/
    │   │   ├── HomePage.tsx        # Landing with tool cards
    │   │   ├── CodeLensView.tsx    # Full-height chat layout
    │   │   ├── IngestBar.tsx       # Repo URL input + status
    │   │   ├── QueryPanel.tsx      # Chat window with history
    │   │   ├── ChatMessage.tsx     # Per-message Q+A bubble
    │   │   ├── MarkdownContent.tsx # react-markdown + syntax highlighting
    │   │   ├── PipelineSteps.tsx   # Animated pipeline progress
    │   │   └── SourceCard.tsx      # Cited source display
    │   ├── hooks/
    │   │   ├── useIngest.ts        # Ingestion API call
    │   │   └── useQuery.ts         # SSE stream consumer
    │   └── types/index.ts
    └── vite.config.ts
```

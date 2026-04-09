# CodeLens — Interview Reference

---

## 30-Second Pitch

"I built a production-grade Q&A system over GitHub repositories. You paste a repo URL, it ingests the codebase using AST parsing — not naive text splitting — and then you can ask natural language questions and get answers with exact file paths, function names, and line numbers cited. The retrieval uses hybrid search: dense vector embeddings plus BM25 for keyword matching, fused with Reciprocal Rank Fusion, then reranked with a cross-encoder. The query pipeline runs as a LangGraph state graph and streams responses token by token to the frontend via SSE."

---

## 2-Minute Deep Dive

"The project has two main pipelines — ingestion and querying.

**Ingestion:** When a user submits a GitHub URL, I fetch the source files using PyGitHub. Instead of splitting files by character count like most RAG tutorials do, I use tree-sitter to parse the AST and extract function and class definitions as individual chunks. Each chunk carries metadata: file path, function name, class name, language, and start/end line numbers. These chunks are embedded using Gemini's embedding model at 768 dimensions and stored in Supabase pgvector with an HNSW index. I also support incremental ingestion — every repo stores its latest commit SHA, and on re-ingest I only process the files that actually changed.

**Query:** The query pipeline is a LangGraph StateGraph with four nodes. First, embed the question. Second, hybrid retrieval — I run the embedding against pgvector for semantic similarity, and separately run BM25 for keyword matching. The two ranked lists are merged using Reciprocal Rank Fusion. Third, rerank the top 20 results down to 5 using FlashRank, a local cross-encoder. Fourth, send the top 5 chunks plus the question to the LLM and stream the response back via SSE.

The frontend is React with Vite, deployed on Vercel. Backend is FastAPI in Docker on Render. The streaming uses Server-Sent Events — the frontend receives status events as each pipeline step completes, then LLM tokens one by one."

---

## Full Pipeline — Every Step Explained

### Ingestion

**Step 1 — GitHub fetch**
- `PyGitHub` fetches the repo's file tree in one API call, then downloads supported files (.py, .js, .java)
- Skips: node_modules, .git, dist, build, test files
- Returns `(files, latest_commit_sha)`
- Why `asyncio.to_thread()`: PyGitHub is synchronous — wrapping it prevents blocking FastAPI's async event loop

**Step 2 — AST chunking (tree-sitter)**
- tree-sitter builds a concrete syntax tree for each file
- We walk the tree looking for `function_definition`, `class_definition` nodes
- Each node becomes one chunk: its full source text + metadata
- For methods inside classes, we track the parent class name
- Why not naive splitting: a 500-char split might start in the middle of a function and cut off the return statement. The LLM gets incomplete context and gives wrong answers.

**Step 3 — Embedding**
- `GoogleGenerativeAIEmbeddings` with `models/gemini-embedding-001`
- `output_dimensionality=768` — truncates from default 3072 to stay within pgvector's HNSW index limit (2000 dims max)
- Batched in groups of 50 with `asyncio.Semaphore(3)` to respect rate limits
- `tenacity` retry with exponential backoff (min 40s) on 429 errors

**Step 4 — Storage**
- `create_repo()` first — chunks have a foreign key to repo_id
- `insert_chunks()` in batches of 100 to avoid Supabase request size limits

**Incremental ingestion**
- Store commit SHA per repo in the `repos` table
- On re-ingest: compare stored SHA with current HEAD
- If same → skip (already up to date)
- If different → call GitHub compare API to get the exact diff
- `added` files → ingest fresh
- `modified` files → delete old chunks, ingest fresh
- `removed` files → delete chunks only
- `renamed` files → treated as removed (old path) + added (new path)

---

### Query Pipeline (LangGraph)

**State (TypedDict)**
```
question           → user's question string
repo_id            → which repo to search
question_embedding → vector for the question
retrieved_chunks   → top 20 from hybrid search
reranked_chunks    → top 5 after reranking
answer             → final LLM response
```

**Node 1 — embed_query**
- Calls `embed_text(question)` → Gemini embedding
- Returns `{"question_embedding": [...]}`

**Node 2 — hybrid_retrieve**
- Vector search: `match_chunks` Postgres RPC function, cosine similarity (`<=>` operator), top 20
- BM25 search: tokenize all chunk content (whitespace split + lowercase), build `BM25Okapi` index, score question tokens against it, top 20
- BM25 index is cached in-memory per `repo_id`, evicted on re-ingestion
- Merge with RRF: `score = 1 / (60 + rank + 1)` per list, sum scores, deduplicate by chunk ID, sort descending
- Why k=60: standard default, dampens the impact of rank 1 vs rank 2

**Node 3 — rerank**
- FlashRank `Ranker` loads `ms-marco-TinyBERT-L-2-v2` cross-encoder locally
- Cross-encoder: looks at (query, chunk) together, not independently — more accurate than bi-encoders
- Re-scores all 20 candidates, keeps top 5
- Why two stages: cross-encoders are O(n) expensive — only feasible on 20 candidates, not the full corpus

**Node 4 — generate**
- Builds context string from top 5 chunks with source citations
- Uses XML tags in prompt (`<context>`, `<question>`) instead of markdown headers
- Why XML: code chunks may contain `## headers` in comments/docstrings which would confuse a markdown-based prompt structure
- Streams via `llm.astream()` — tokens arrive as they're generated

---

## Why Each Technology Was Chosen

| Decision | Why |
|---|---|
| **tree-sitter over LangChain splitters** | LangChain's code splitter is heuristic (regex-based). tree-sitter builds a real AST — guaranteed to produce syntactically complete chunks. Handles nested classes, decorators, type hints correctly. |
| **pgvector over Pinecone/ChromaDB** | pgvector runs inside PostgreSQL. For a production system, having vectors co-located with relational metadata means one database, one connection, one backup strategy. Also: free with Supabase. |
| **HNSW index over IVFFlat** | Both have a 2000-dim limit in pgvector. HNSW has better recall and doesn't require a training step (IVFFlat needs to know the number of clusters upfront). |
| **BM25 alongside vector search** | Vector search misses exact symbol matches. If a developer asks "where is `validate_token` called?", semantic search returns "authentication-related code" — BM25 finds the exact function name. |
| **RRF over score normalization** | Vector similarity scores and BM25 scores are on completely different scales. Normalizing them requires knowing the distribution. RRF only uses rank positions — no normalization needed, works well in practice. |
| **FlashRank over Cohere Rerank** | FlashRank runs locally — no API call, no latency added, no cost per rerank. For top-20 reranking the model size is fine. Cohere Rerank adds a network round-trip and API cost. |
| **LangGraph over a plain function chain** | LangGraph gives explicit state management. Each node receives the full state and returns only what it changed — LangGraph merges it. This makes it easy to add nodes (e.g. query classification, citation checking) without refactoring the whole pipeline. Also: astream_events for observability. |
| **SSE over WebSockets** | SSE is unidirectional (server → client), which is exactly what we need for streaming LLM output. WebSockets are bidirectional and add complexity. SSE works over plain HTTP/2, no upgrade handshake needed. |
| **Groq over OpenAI** | Groq's free tier gives 1000 requests/day with zero billing setup. For a portfolio demo that's more than sufficient. LLaMA 3.3 70B quality is competitive with GPT-4o-mini. |

---

## Numbers to Know

| Metric | Value |
|---|---|
| Embedding dimensions | 768 (truncated from 3072) |
| pgvector HNSW index limit | 2000 dims max |
| Embedding batch size | 50 chunks per batch |
| Concurrent embedding workers | 3 (Semaphore) |
| Retry backoff on 429 | min 40s, max 120s, 5 attempts |
| Vector retrieval top-k | 20 |
| BM25 retrieval top-k | 20 |
| After reranking | top 5 |
| RRF k constant | 60 |
| FlashRank model | ms-marco-TinyBERT-L-2-v2 (3.26 MB) |
| BM25 insert batch size | 100 chunks |
| Groq free tier | 1000 RPD, 100 RPM |

---

## Anticipated Interview Questions

**Q: Why not just use LangChain's built-in RAG pipeline?**
A: LangChain's default pipeline does naive text splitting and doesn't carry code-specific metadata. We need AST chunking to get function-level granularity and metadata like function name and class name — that's what makes the citations ("see `validate_token` in auth.py line 42") possible. LangGraph lets us build a custom stateful pipeline cleanly.

**Q: How does incremental ingestion work?**
A: Every repo record stores the last ingested commit SHA. When the user re-submits a URL, we compare that SHA with the current HEAD. If they match, we skip. If different, we use GitHub's compare API to get the exact file diff — only added, modified, removed, and renamed files. We delete and re-embed only those files instead of re-processing the whole repo.

**Q: What's Reciprocal Rank Fusion and why use it?**
A: RRF is a rank aggregation algorithm. It assigns each document a score of `1 / (k + rank)` from each ranked list, then sums the scores. A document that ranks highly in both lists gets a higher combined score than one that only ranks in one. We use it because vector similarity scores and BM25 scores are on different scales — you can't just average them. RRF only uses positions, not raw scores, so no normalization is needed.

**Q: Why does the reranker help if you already have good retrieval?**
A: The retrieval (vector + BM25) uses bi-encoder models — they embed the query and each document independently and compare them. Fast, but less accurate. A cross-encoder (reranker) looks at the query and document together in one pass — it can model interactions between them. Much more accurate, but too slow to run on thousands of documents. Two-stage solves this: retrieve broadly with fast bi-encoders, then rerank the small candidate set with the accurate cross-encoder.

**Q: Why SSE instead of polling?**
A: Polling requires the client to repeatedly make HTTP requests — wasteful and adds latency between tokens. SSE keeps a single HTTP connection open and lets the server push events as they happen. For LLM token streaming this gives a "live typing" effect with no extra requests. Simpler than WebSockets for a one-directional stream.

**Q: How do you handle GitHub API rate limits?**
A: PyGitHub uses the REST API which has 5000 requests/hour per token. For the embedding side, Gemini has stricter per-minute limits — we use `asyncio.Semaphore(3)` to cap concurrent embedding calls to 3, and `tenacity` with exponential backoff (starting at 40 seconds) to retry on 429 errors.

**Q: What would you improve with more time?**
A: A few things — first, the incremental ingestion fetches the full repo to get the latest SHA (an optimization would be a separate lightweight call to get HEAD SHA). Second, I'd add query classification to route "what does X do?" vs "find all usages of Y" differently. Third, I'd add an eval pipeline to measure retrieval quality (hit rate, MRR) as the corpus changes.

---

## How to Demo

1. Open the live URL
2. Paste `https://github.com/BaseMax/SimpleFastPyAPI` in the ingest bar
3. Click Index — it will say "Up to date" (already indexed from testing)
4. Ask: **"How does authentication work in this repo?"**
5. Watch: pipeline steps animate (Embed → Retrieve → Rerank → Generate), then answer streams in with cited sources
6. Ask a follow-up: **"Show me the User model"**
7. The chat stays persistent — show that history is kept across questions
8. Point out: sources panel shows file path, function name, exact line numbers

Good questions to ask during demo to show depth:
- "What database models are defined?"
- "How are HTTP exceptions handled?"
- "What does the health check endpoint do?"

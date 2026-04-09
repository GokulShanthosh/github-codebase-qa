"""
LangGraph Nodes — one async function per node in the query pipeline.

Each node:
  - receives the full QueryState
  - does one job
  - returns a dict with only the fields it updated
  LangGraph merges that dict back into state automatically.

Pipeline: embed_query → hybrid_retrieve → rerank → generate
"""
from langchain_groq import ChatGroq
from rank_bm25 import BM25Okapi
from flashrank import Ranker, RerankRequest

from app.graph.state import QueryState
from app.core.ingestion.embedder import embed_text
from app.db import vector_store
from app.core.config import settings


# ---------------------------------------------------------------------------
# BM25 Cache
# ---------------------------------------------------------------------------
# WHY: BM25 index is built from ALL chunks of a repo.
# Fetching all chunks + rebuilding the index on every query is expensive.
# We cache the index per repo_id. Built once on first query, reused after.
# Evict by calling bm25_cache.pop(repo_id) after re-ingestion.

bm25_cache: dict[str, tuple[BM25Okapi, list[dict]]] = {}
# Structure: { repo_id: (bm25_index, all_chunks_list) }
# We store chunks alongside the index so we can map BM25 scores back to chunk dicts


# ---------------------------------------------------------------------------
# Node 1: embed_query
# ---------------------------------------------------------------------------

async def embed_query(state: QueryState) -> dict:
    """
    Convert the user's question into a vector embedding.

    WHY first node: all downstream nodes need the embedding.
    Doing it once here means no node has to call the embedding API themselves.
    """
    embedding = await embed_text(state["question"])
    return {"question_embedding": embedding}


# ---------------------------------------------------------------------------
# Node 2: hybrid_retrieve
# ---------------------------------------------------------------------------

async def hybrid_retrieve(state: QueryState) -> dict:
    """
    Retrieve relevant chunks using two methods in parallel:
      1. Vector search  — semantic similarity (good for conceptual questions)
      2. BM25 search    — keyword matching (good for exact symbol/function lookups)

    Results from both are merged using Reciprocal Rank Fusion (RRF).

    WHY two methods: neither alone is sufficient.
    "How does auth work?" → needs semantic search
    "Where is jwt.decode called?" → needs keyword search
    Running both and merging gives the best of both worlds.
    """
    repo_id = state["repo_id"]
    question = state["question"]
    question_embedding = state["question_embedding"]

    # --- Vector search (async, hits Supabase pgvector) ---
    vector_results = await vector_store.similarity_search(
        query_embedding=question_embedding,
        repo_id=repo_id,
        top_k=20,
    )

    # --- BM25 search (in-memory, uses cached index) ---
    bm25_results = await _bm25_search(repo_id, question, top_k=20)

    # --- Merge using Reciprocal Rank Fusion ---
    merged = _reciprocal_rank_fusion(vector_results, bm25_results)

    return {"retrieved_chunks": merged}


async def _bm25_search(repo_id: str, question: str, top_k: int) -> list[dict]:
    """
    Build (or retrieve from cache) a BM25 index for this repo,
    then search it with the user's question.
    """
    # Cache miss — build the index for the first time
    if repo_id not in bm25_cache:
        all_chunks = await vector_store.get_all_chunks_content(repo_id)

        if not all_chunks:
            return []

        # WHY tokenize by splitting on whitespace + lowercasing:
        # BM25 works on token frequency. Simple whitespace tokenization
        # is sufficient for code — function names, keywords are space-separated.
        tokenized = [chunk["content"].lower().split() for chunk in all_chunks]
        index = BM25Okapi(tokenized)

        bm25_cache[repo_id] = (index, all_chunks)

    index, all_chunks = bm25_cache[repo_id]

    # Score the question against all chunks
    query_tokens = question.lower().split()
    scores = index.get_scores(query_tokens)

    # Pair each chunk with its BM25 score, sort descending, take top_k
    scored = sorted(
        zip(scores, all_chunks),
        key=lambda x: x[0],
        reverse=True,
    )

    return [chunk for _, chunk in scored[:top_k]]


def _reciprocal_rank_fusion(
    vector_results: list[dict],
    bm25_results: list[dict],
    k: int = 60,
) -> list[dict]:
    """
    Merge two ranked lists into one using Reciprocal Rank Fusion.

    WHY RRF instead of just concatenating:
    Concatenating gives duplicates and no clear ranking.
    RRF assigns each chunk a score based on its rank in each list:
      score = 1/(k + rank)
    A chunk ranked #1 in both lists gets a higher combined score
    than a chunk ranked #1 in only one list.
    k=60 is the standard default — dampens the impact of top ranks.
    """
    scores: dict[str, float] = {}
    chunk_map: dict[str, dict] = {}

    for rank, chunk in enumerate(vector_results):
        cid = chunk["id"]
        scores[cid] = scores.get(cid, 0) + 1 / (k + rank + 1)
        chunk_map[cid] = chunk

    for rank, chunk in enumerate(bm25_results):
        cid = chunk["id"]
        scores[cid] = scores.get(cid, 0) + 1 / (k + rank + 1)
        chunk_map[cid] = chunk

    # Sort by combined RRF score descending
    sorted_ids = sorted(scores, key=lambda cid: scores[cid], reverse=True)
    return [chunk_map[cid] for cid in sorted_ids]


# ---------------------------------------------------------------------------
# Node 3: rerank
# ---------------------------------------------------------------------------

async def rerank(state: QueryState) -> dict:
    """
    Re-score the merged retrieved chunks using a cross-encoder model (FlashRank).

    WHY rerank after retrieval:
    Vector search and BM25 use lightweight models for speed — they retrieve
    broadly. A cross-encoder (reranker) is slower but more accurate — it
    looks at the query AND each chunk together to score relevance precisely.
    Two-stage: retrieve fast → rerank accurately → keep only the best.

    WHY FlashRank: runs locally, no API cost, fast enough for top-20 chunks.
    """
    ranker = Ranker()  # loads a lightweight cross-encoder model locally

    passages = [
        {"id": i, "text": chunk["content"]}
        for i, chunk in enumerate(state["retrieved_chunks"])
    ]

    request = RerankRequest(query=state["question"], passages=passages)
    results = ranker.rerank(request)

    # Results are sorted by relevance score — take top 5
    # Map back to original chunk dicts using the id we assigned above
    top_indices = [r.get("id") for r in results[:5]]
    reranked = [state["retrieved_chunks"][i] for i in top_indices]

    return {"reranked_chunks": reranked}


# ---------------------------------------------------------------------------
# Node 4: generate
# ---------------------------------------------------------------------------

async def generate(state: QueryState) -> dict:
    """
    Send the reranked chunks + user question to Gemini and get the final answer.

    WHY include file_path and line numbers in prompt:
    The LLM needs this to generate cited answers like:
    "The charge function in services/payment.py (line 12) handles this by..."
    Without metadata, answers are vague and unverifiable.
    """
    llm = ChatGroq(
        model=settings.groq_chat_model,
        api_key=settings.groq_api_key,
        temperature=0,
        # WHY temperature=0: we want deterministic, factual answers grounded
        # in the retrieved code — not creative generation.
    )

    # Build context string from reranked chunks with source citations
    context_parts = []
    for chunk in state["reranked_chunks"]:
        source = f"{chunk['file_path']} | {chunk.get('name', 'unknown')} | lines {chunk['start_line']}-{chunk['end_line']}"
        context_parts.append(f"### Source: {source}\n```\n{chunk['content']}\n```")

    context = "\n\n".join(context_parts)

    # WHY XML tags instead of markdown headers:
    # Code chunks may contain strings like "## Question" in comments/docstrings.
    # Markdown headers would confuse the LLM about where context ends and the
    # question begins (prompt injection via code content).
    # XML tags are structurally unambiguous and rarely appear in source code.
    prompt = f"""You are a code assistant. Answer the question using ONLY the code context provided below.
Always cite the source file and function name when referencing code.
If the answer cannot be found in the context, say so clearly — do not guess.

<context>
{context}
</context>

<question>
{state['question']}
</question>
"""

    response = await llm.ainvoke(prompt)
    return {"answer": response.content}

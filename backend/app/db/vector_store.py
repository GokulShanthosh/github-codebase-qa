"""
Vector Store — all async database operations for repos and chunks.

WHY ASYNC:
FastAPI is async. If DB calls are synchronous, they block the event loop
while waiting for network I/O to Supabase. Async lets other requests be
served while DB operations are in flight.
"""
from datetime import datetime, timezone
from supabase import acreate_client, AsyncClient
from app.core.config import settings


# ---------------------------------------------------------------------------
# Client — async singleton
# ---------------------------------------------------------------------------

# WHY singleton: client initialization is expensive — do it once.
# WHY AsyncClient: non-blocking DB operations, compatible with FastAPI's
# async event loop. Never use the sync client inside async endpoints.
_client: AsyncClient | None = None


async def _get_client() -> AsyncClient:
    global _client
    if _client is None:
        _client = await acreate_client(settings.supabase_url, settings.supabase_service_key)
    return _client


# ---------------------------------------------------------------------------
# Repo operations
# ---------------------------------------------------------------------------

async def get_repo(repo_url: str) -> dict | None:
    """
    Check if a repo has been ingested before.
    Returns the repo row if found, None if not.
    New repo → full ingest. Existing repo → compare SHAs for incremental update.
    """
    client = await _get_client()
    result = await client.table("repos").select("*").eq("repo_url", repo_url).execute()
    return result.data[0] if result.data else None


async def create_repo(repo_url: str, repo_name: str, commit_sha: str) -> dict:
    """Insert a new repo record after successful ingestion."""
    client = await _get_client()
    result = await client.table("repos").insert({
        "repo_url": repo_url,
        "repo_name": repo_name,
        "last_commit_sha": commit_sha,
        "last_ingested_at": datetime.now(timezone.utc).isoformat(),
        "status": "completed",
    }).execute()
    return result.data[0]


async def update_repo_sha(repo_id: str, new_sha: str) -> None:
    """Update the commit SHA after incremental re-ingestion."""
    client = await _get_client()
    await client.table("repos").update({
        "last_commit_sha": new_sha,
        "last_ingested_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", repo_id).execute()


async def delete_chunks_for_file(repo_id: str, file_path: str) -> None:
    """
    Delete all chunks for a specific file.
    Called before re-ingesting modified or renamed files to prevent duplicates.
    """
    client = await _get_client()
    await client.table("chunks").delete()\
        .eq("repo_id", repo_id)\
        .eq("file_path", file_path)\
        .execute()


# ---------------------------------------------------------------------------
# Chunk operations
# ---------------------------------------------------------------------------

async def insert_chunks(chunks: list[dict]) -> None:
    """
    Bulk insert code chunks.

    WHY batch insert: one network round trip per 100 chunks instead of
    one per chunk. A large repo with 3000 chunks = 30 round trips, not 3000.
    """
    client = await _get_client()
    BATCH_SIZE = 100

    for i in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[i:i + BATCH_SIZE]
        await client.table("chunks").insert(batch).execute()


async def similarity_search(
    query_embedding: list[float],
    repo_id: str,
    top_k: int = 20,
) -> list[dict]:
    """
    Find top_k most similar chunks to a query embedding via cosine similarity.

    WHY top_k=20: We over-fetch because the reranker will trim to the best 5.
    Better to give the reranker more options than too few.

    WHY RPC: The pgvector <=> operator only works inside PostgreSQL.
    We wrap it in a Postgres function and call it via Supabase RPC.
    """
    client = await _get_client()
    result = await client.rpc("match_chunks", {
        "query_embedding": query_embedding,
        "match_repo_id": repo_id,
        "match_count": top_k,
    }).execute()
    return result.data


async def get_all_chunks_content(repo_id: str) -> list[dict]:
    """
    Fetch all chunks for a repo (without embeddings).
    Used to build the in-memory BM25 index for keyword search.

    WHY no embeddings: embeddings are large float arrays — fetching them
    for BM25 wastes bandwidth. BM25 only needs the raw text content.
    """
    client = await _get_client()
    result = await client.table("chunks")\
        .select("id, content, file_path, name, class_name, node_type, language, start_line, end_line")\
        .eq("repo_id", repo_id)\
        .execute()
    return result.data

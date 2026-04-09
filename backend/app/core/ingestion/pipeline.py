"""
Ingestion Pipeline — orchestrates the full flow from repo URL to stored vectors.

THIS IS THE BRAIN OF INGESTION. It coordinates:
  github_loader  → fetch source files + commit SHA
  code_chunker   → split files into semantic chunks
  embedder       → convert chunk text to vectors
  vector_store   → persist everything to Supabase

TWO MODES:
  1. Full ingestion   — repo seen for the first time
  2. Incremental      — repo exists, compare SHAs, only process changed files
"""
import asyncio
from app.core.logger import get_logger
from app.core.ingestion.github_loader import (
    load_repo,
    get_changed_files,
    SourceFile,
    SUPPORTED_EXTENSIONS,
)
from app.core.ingestion.code_chunker import chunk_file
from app.core.ingestion.embedder import embed_chunks
from app.db import vector_store

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------

class IngestionResult:
    def __init__(self, status: str, message: str, chunks_stored: int = 0, repo_id: str | None = None):
        self.status = status          # "created" | "updated" | "skipped" | "error"
        self.message = message
        self.chunks_stored = chunks_stored
        self.repo_id = repo_id        # needed by frontend to make /query requests

    def dict(self):
        return {
            "status": self.status,
            "message": self.message,
            "chunks_stored": self.chunks_stored,
            "repo_id": self.repo_id,
        }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def ingest_repo(repo_url: str) -> IngestionResult:
    """
    Main entry point. Called by the FastAPI endpoint when a user submits a repo URL.
    Decides between full ingestion and incremental update automatically.
    """
    try:
        logger.info(f"Ingestion requested for: {repo_url}")
        existing_repo = await vector_store.get_repo(repo_url)

        if existing_repo is None:
            logger.info("New repo — starting full ingestion")
            return await _full_ingest(repo_url)
        else:
            logger.info("Existing repo — starting incremental ingestion")
            return await _incremental_ingest(repo_url, existing_repo)

    except Exception as e:
        logger.error(f"Ingestion failed for {repo_url}: {e}")
        return IngestionResult(status="error", message=str(e))


# ---------------------------------------------------------------------------
# Full ingestion — new repo, never seen before
# ---------------------------------------------------------------------------

async def _full_ingest(repo_url: str) -> IngestionResult:
    """
    Fetch all source files, chunk them, embed them, store everything.
    Called only when the repo URL doesn't exist in our DB yet.
    """
    # Step 1: Fetch all source files from GitHub + get latest commit SHA
    # WHY capture SHA here: we store it so future ingestions can compare
    # and only re-process files that actually changed
    files, latest_sha = await asyncio.to_thread(load_repo, repo_url)
    # WHY to_thread: PyGitHub uses synchronous HTTP calls (not async-native).
    # Running it directly in async code would block the event loop.
    # asyncio.to_thread() runs it in a thread pool — non-blocking.
    logger.info(f"Fetched {len(files)} source files from GitHub")

    if not files:
        return IngestionResult(
            status="error",
            message="No supported source files found in this repository."
        )

    # Step 2: Chunk all files using AST parser
    all_chunks = []
    for file in files:
        chunks = chunk_file(file.content, file.language, file.file_path)
        all_chunks.extend(chunks)

    if not all_chunks:
        return IngestionResult(
            status="error",
            message="No functions or classes found to index."
        )

    logger.info(f"Generated {len(all_chunks)} chunks from {len(files)} files")

    # Step 3: Embed all chunk content concurrently
    # We pass just the text content — embedder returns vectors in same order
    texts = [c.content for c in all_chunks]
    logger.info(f"Embedding {len(texts)} chunks...")
    vectors = await embed_chunks(texts)
    logger.info("Embedding complete")

    # Step 4: Create the repo record first to get its ID
    # WHY create repo before chunks: chunks have a foreign key to repo_id.
    # We need the repo row to exist before inserting chunk rows.
    repo_name = _parse_repo_name(repo_url)
    repo_record = await vector_store.create_repo(repo_url, repo_name, latest_sha)
    repo_id = repo_record["id"]

    # Step 5: Build chunk dicts pairing each chunk with its embedding
    chunk_rows = [
        {
            "repo_id": repo_id,
            "file_path": chunk.metadata["file_path"],
            "name": chunk.metadata["name"],
            "class_name": chunk.metadata["class_name"],
            "node_type": chunk.metadata["node_type"],
            "language": chunk.metadata["language"],
            "start_line": chunk.metadata["start_line"],
            "end_line": chunk.metadata["end_line"],
            "content": chunk.content,
            "embedding": vector,
        }
        for chunk, vector in zip(all_chunks, vectors)
    ]

    # Step 6: Persist to Supabase in batches
    logger.info(f"Storing {len(chunk_rows)} chunks to Supabase...")
    await vector_store.insert_chunks(chunk_rows)
    logger.info(f"Full ingestion complete for {repo_name}")

    return IngestionResult(
        status="created",
        message=f"Successfully ingested {repo_name}",
        chunks_stored=len(chunk_rows),
        repo_id=repo_id,
    )


# ---------------------------------------------------------------------------
# Incremental ingestion — repo exists, only process changed files
# ---------------------------------------------------------------------------

async def _incremental_ingest(repo_url: str, existing_repo: dict) -> IngestionResult:
    """
    Compare the stored commit SHA with the latest SHA.
    If same → nothing changed, skip.
    If different → fetch only changed files, update only those chunks.
    """
    stored_sha = existing_repo["last_commit_sha"]
    repo_id = existing_repo["id"]

    # Step 1: Get latest commit SHA without downloading any files yet
    # WHY: cheap check — one API call to see if anything changed at all
    _, latest_sha = await asyncio.to_thread(load_repo, repo_url)
    # Note: load_repo fetches files too — optimization opportunity:
    # a separate get_latest_sha() function would avoid fetching files here.
    # Marked as a known improvement.

    if stored_sha == latest_sha:
        return IngestionResult(
            status="skipped",
            message="Repository is already up to date.",
            repo_id=repo_id,
        )

    # Step 2: Find exactly which files changed between the two SHAs
    changed_files = await asyncio.to_thread(
        get_changed_files, repo_url, stored_sha, latest_sha
    )

    if not changed_files:
        await vector_store.update_repo_sha(repo_id, latest_sha)
        return IngestionResult(
            status="updated",
            message="SHA updated. No supported file changes detected.",
            repo_id=repo_id,
        )

    # Step 3: Process all changed files concurrently
    # WHY gather: each file is independent — fetch, chunk, embed, store.
    # No file depends on another. Running them in parallel cuts total time
    # from (n files × per-file time) to ~(1 × per-file time).
    results = await asyncio.gather(*[
        _process_changed_file(repo_id, repo_url, file_path, status)
        for file_path, status in changed_files.items()
    ])

    total_chunks = sum(results)

    # Step 4: Update the stored SHA to latest
    await vector_store.update_repo_sha(repo_id, latest_sha)

    return IngestionResult(
        status="updated",
        message=f"Incremental update complete. {len(changed_files)} files processed.",
        chunks_stored=total_chunks,
        repo_id=repo_id,
    )


async def _process_changed_file(
    repo_id: str,
    repo_url: str,
    file_path: str,
    status: str,
) -> int:
    """
    Handle one changed file. Returns number of chunks stored (0 for removals).
    Designed to run concurrently with other files via asyncio.gather.
    """
    if status == "removed":
        await vector_store.delete_chunks_for_file(repo_id, file_path)
        return 0

    # For modified: delete stale chunks first
    if status == "modified":
        await vector_store.delete_chunks_for_file(repo_id, file_path)

    file = await asyncio.to_thread(_fetch_single_file, repo_url, file_path)
    if file is None:
        return 0

    chunks = chunk_file(file.content, file.language, file.file_path)
    if not chunks:
        return 0

    texts = [c.content for c in chunks]
    vectors = await embed_chunks(texts)

    chunk_rows = [
        {
            "repo_id": repo_id,
            "file_path": chunk.metadata["file_path"],
            "name": chunk.metadata["name"],
            "class_name": chunk.metadata["class_name"],
            "node_type": chunk.metadata["node_type"],
            "language": chunk.metadata["language"],
            "start_line": chunk.metadata["start_line"],
            "end_line": chunk.metadata["end_line"],
            "content": chunk.content,
            "embedding": vector,
        }
        for chunk, vector in zip(chunks, vectors)
    ]

    await vector_store.insert_chunks(chunk_rows)
    return len(chunk_rows)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_repo_name(repo_url: str) -> str:
    url = repo_url.rstrip("/")
    parts = url.split("/")
    return f"{parts[-2]}/{parts[-1]}"


def _fetch_single_file(repo_url: str, file_path: str) -> SourceFile | None:
    """
    Fetch a single file's content from GitHub.
    Used during incremental ingestion to re-embed only changed files.
    WHY separate from load_repo: load_repo fetches the entire repo.
    For incremental updates we only need one file at a time.
    """
    import base64
    from github import Github
    from app.core.config import settings

    owner_repo = _parse_repo_name(repo_url)
    g = Github(settings.github_token)
    repo = g.get_repo(owner_repo)

    ext = "." + file_path.rsplit(".", 1)[-1] if "." in file_path else ""
    language = SUPPORTED_EXTENSIONS.get(ext)
    if not language:
        return None

    try:
        file_content = repo.get_contents(file_path)
        content = base64.b64decode(file_content.content).decode("utf-8", errors="ignore")
        return SourceFile(
            repo_name=owner_repo,
            file_path=file_path,
            language=language,
            content=content,
        )
    except Exception:
        return None

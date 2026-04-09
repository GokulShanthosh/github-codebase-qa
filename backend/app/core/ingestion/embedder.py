"""
Embedder — converts text into vector embeddings using Google gemini-embedding-001.

WHY ASYNC:
FastAPI runs on an async event loop. Synchronous blocking calls block the event loop.
Async lets other requests be served while waiting for the Gemini API response.

WHY output_dimensionality=768:
gemini-embedding-001 outputs 3072 dims by default.
pgvector HNSW/IVFFlat indexes have a hard 2000 dimension limit.
We truncate to 768 — supported without quality loss, stays within index limits.

WHY SEMAPHORE + RETRY:
Free tier limit is 100 requests/minute. Firing all batches concurrently
without control hits this instantly. A semaphore caps concurrent requests.
Tenacity retries automatically on 429 with exponential backoff.

CRITICAL RULE: embedding model AND output_dimensionality must be identical
for chunks and queries. Mismatched models = meaningless similarity scores.
"""
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from app.core.logger import get_logger
from app.core.config import settings

logger = get_logger(__name__)

OUTPUT_DIMS = 768
BATCH_SIZE = 50
MAX_CONCURRENT = 3  # max parallel requests to Gemini at once


# ---------------------------------------------------------------------------
# Embeddings client — singleton
# ---------------------------------------------------------------------------

_embeddings: GoogleGenerativeAIEmbeddings | None = None


def _get_embeddings() -> GoogleGenerativeAIEmbeddings:
    global _embeddings
    if _embeddings is None:
        _embeddings = GoogleGenerativeAIEmbeddings(
            model=settings.gemini_embedding_model,
            google_api_key=settings.google_api_key,
        )
    return _embeddings


# ---------------------------------------------------------------------------
# Retry logic
# ---------------------------------------------------------------------------

def _is_rate_limit(exc: Exception) -> bool:
    """Tell tenacity to retry only on 429 rate limit errors."""
    return "429" in str(exc) or "RESOURCE_EXHAUSTED" in str(exc)


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=40, max=120),
    retry=retry_if_exception(_is_rate_limit),
    reraise=True,
)
async def _embed_batch(batch: list[str]) -> list[list[float]]:
    """
    Embed one batch with automatic retry on rate limit.
    wait_exponential: first retry after 40s, then 80s, up to 120s.
    This matches the ~37s retry delay Google suggests in the error message.
    """
    embeddings = _get_embeddings()
    return await embeddings.aembed_documents(batch, output_dimensionality=OUTPUT_DIMS)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def embed_text(text: str) -> list[float]:
    """Embed a single query text. Returns 768-dim vector."""
    embeddings = _get_embeddings()
    return await embeddings.aembed_query(text, output_dimensionality=OUTPUT_DIMS)


async def embed_chunks(texts: list[str]) -> list[list[float]]:
    """
    Embed a list of texts with rate limit protection.

    WHY semaphore: limits concurrent Gemini requests to MAX_CONCURRENT.
    Instead of firing 20 batches at once (instant 429), we keep at most
    3 in-flight at any time — stays under the rate limit.
    """
    batches = [
        texts[i:i + BATCH_SIZE]
        for i in range(0, len(texts), BATCH_SIZE)
    ]

    logger.info(f"Embedding {len(texts)} texts in {len(batches)} batches (max {MAX_CONCURRENT} concurrent)")

    semaphore = asyncio.Semaphore(MAX_CONCURRENT)

    async def _embed_with_semaphore(batch: list[str]) -> list[list[float]]:
        async with semaphore:
            return await _embed_batch(batch)

    results = await asyncio.gather(*[
        _embed_with_semaphore(batch) for batch in batches
    ])

    return [vector for batch_result in results for vector in batch_result]

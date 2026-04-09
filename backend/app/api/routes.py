"""
Routes — HTTP only. No business logic here.
Receive request → call service → return response.
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.schemas.ingestion import IngestRequest, IngestResponse
from app.schemas.query import QueryRequest
from app.core.ingestion.pipeline import ingest_repo
from app.services.query_service import stream_query
from app.graph.nodes import bm25_cache

router = APIRouter()


@router.post("/ingest", response_model=IngestResponse)
async def ingest(request: IngestRequest):
    result = await ingest_repo(request.repo_url)

    if result.status == "error":
        raise HTTPException(status_code=400, detail=result.message)

    # Evict stale BM25 cache on re-ingestion
    if result.status == "updated" and result.repo_id:
        bm25_cache.pop(result.repo_id, None)

    return IngestResponse(
        status=result.status,
        message=result.message,
        chunks_stored=result.chunks_stored,
        repo_id=result.repo_id,
    )


@router.post("/query")
async def query(request: QueryRequest):
    """
    Streams the query pipeline as SSE events.

    WHY StreamingResponse with text/event-stream:
    This is the SSE content type. The browser's EventSource API recognises
    it and automatically reconnects if the connection drops.
    media_type tells the browser to treat each "data: ..." line as an event.
    """
    return StreamingResponse(
        stream_query(request.question, request.repo_id),
        media_type="text/event-stream",
        headers={
            # Prevents nginx/proxies from buffering the stream
            "X-Accel-Buffering": "no",
            "Cache-Control": "no-cache",
        }
    )

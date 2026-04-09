"""
Query Service — business logic for running the query pipeline with SSE streaming.

WHY SSE INSTEAD OF WAITING FOR FULL RESPONSE:
The query pipeline has 4 steps that collectively take 5-10 seconds.
Without streaming, the user stares at a blank screen the whole time.
SSE pushes progress updates and answer tokens to the frontend in real time
as each step completes — much better UX.

SSE FORMAT:
Each event is a JSON string prefixed with "data: " and ending with "\n\n".
The frontend listens with EventSource and handles each event type.

EVENT TYPES:
  status  → node started/completed (embed, retrieve, rerank)
  token   → one LLM output token (streamed word by word)
  sources → citation list after generation completes
  error   → something went wrong
  done    → stream complete, frontend closes connection
"""
import json
from typing import AsyncGenerator
from langchain_groq import ChatGroq
from app.graph.workflow import query_graph
from app.graph.nodes import bm25_cache
from app.core.ingestion.embedder import embed_text
from app.db import vector_store
from app.graph.nodes import hybrid_retrieve as run_hybrid_retrieve, rerank as run_rerank
from app.core.config import settings


def _event(type: str, **kwargs) -> str:
    """
    Format a single SSE event.
    SSE protocol requires: "data: <payload>\n\n"
    The double newline signals end of one event to the browser's EventSource.
    """
    return f"data: {json.dumps({'type': type, **kwargs})}\n\n"


async def stream_query(question: str, repo_id: str) -> AsyncGenerator[str, None]:
    """
    Run the full query pipeline and yield SSE events at each stage.

    WHY not use query_graph.astream_events() directly:
    astream_events gives low-level LangGraph internals. We want clean,
    user-friendly status messages and token-level streaming for the LLM.
    So we run each node manually, yielding status events between steps,
    and stream LLM tokens directly instead of waiting for full generation.
    """
    try:
        # ── Step 1: Embed query ──────────────────────────────────────────
        yield _event("status", message="Embedding your question...")
        question_embedding = await embed_text(question)

        # ── Step 2: Hybrid retrieval ─────────────────────────────────────
        yield _event("status", message="Searching codebase...")

        # Build partial state to pass into node functions directly
        state = {
            "question": question,
            "repo_id": repo_id,
            "question_embedding": question_embedding,
            "retrieved_chunks": [],
            "reranked_chunks": [],
            "answer": "",
        }

        retrieval_update = await run_hybrid_retrieve(state)
        state.update(retrieval_update)

        # ── Step 3: Rerank ───────────────────────────────────────────────
        yield _event("status", message="Ranking most relevant results...")
        rerank_update = await run_rerank(state)
        state.update(rerank_update)

        # ── Step 4: Stream LLM generation token by token ────────────────
        yield _event("status", message="Generating answer...")

        llm = ChatGroq(
            model=settings.groq_chat_model,
            api_key=settings.groq_api_key,
            temperature=0,
        )

        # Build context with citations (same as generate node)
        context_parts = []
        for chunk in state["reranked_chunks"]:
            source = (
                f"{chunk['file_path']} | "
                f"{chunk.get('name', 'unknown')} | "
                f"lines {chunk['start_line']}-{chunk['end_line']}"
            )
            context_parts.append(f"### Source: {source}\n```\n{chunk['content']}\n```")

        context = "\n\n".join(context_parts)

        prompt = f"""You are a code assistant. Answer the question using ONLY the code context provided below.
Always cite the source file and function name when referencing code.
If the answer cannot be found in the context, say so clearly — do not guess.

<context>
{context}
</context>

<question>
{question}
</question>
"""
        # WHY astream not ainvoke:
        # ainvoke waits for the full response then returns it.
        # astream yields chunks (tokens) as the model generates them.
        # Each chunk has a .content field with the new token(s).
        async for chunk in llm.astream(prompt):
            if chunk.content:
                yield _event("token", content=chunk.content)

        # ── Step 5: Send sources after generation completes ──────────────
        seen = set()
        sources = []
        for chunk in state["reranked_chunks"]:
            key = (chunk["file_path"], chunk.get("name"))
            if key not in seen:
                seen.add(key)
                sources.append({
                    "file_path": chunk["file_path"],
                    "name": chunk.get("name"),
                    "start_line": chunk["start_line"],
                    "end_line": chunk["end_line"],
                })

        yield _event("sources", data=sources)
        yield _event("done")

    except Exception as e:
        yield _event("error", message=str(e))

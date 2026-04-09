"""
LangGraph Workflow — wires nodes and edges into a compiled query pipeline.

WHY THIS EXISTS:
nodes.py defines WHAT each step does.
workflow.py defines the ORDER and CONNECTIONS between steps.
Separating them keeps each file focused on one responsibility.

GRAPH STRUCTURE:
  START → embed_query → hybrid_retrieve → rerank → generate → END
"""
from langgraph.graph import StateGraph, START, END
from app.graph.state import QueryState
from app.graph.nodes import embed_query, hybrid_retrieve, rerank, generate


def build_graph():
    """
    Construct and compile the query pipeline graph.

    WHY compile: LangGraph validates the graph structure at compile time —
    checks for missing nodes, disconnected edges, invalid state transitions.
    A compiled graph is also optimized for execution.
    Fail fast at startup rather than at runtime during a user query.
    """
    # Initialize graph with our state schema
    # WHY pass QueryState: LangGraph uses it to validate that each node
    # returns keys that actually exist in the state — catches typos early.
    graph = StateGraph(QueryState)

    # --- Register nodes ---
    # Each node is an async function that takes state and returns a partial update
    graph.add_node("embed_query", embed_query)
    graph.add_node("hybrid_retrieve", hybrid_retrieve)
    graph.add_node("rerank", rerank)
    graph.add_node("generate", generate)

    # --- Define edges (execution order) ---
    # WHY explicit edges: LangGraph doesn't assume sequential execution.
    # You must explicitly define what runs after what.
    # This gives you full control — you can branch, loop, or run in parallel.
    graph.add_edge(START, "embed_query")
    graph.add_edge("embed_query", "hybrid_retrieve")
    graph.add_edge("hybrid_retrieve", "rerank")
    graph.add_edge("rerank", "generate")
    graph.add_edge("generate", END)

    # Compile validates structure and returns an executable graph
    return graph.compile()


# Module-level compiled graph — created once at startup
# WHY module-level: compiling the graph is expensive.
# We compile once when the module loads and reuse it for every query.
query_graph = build_graph()

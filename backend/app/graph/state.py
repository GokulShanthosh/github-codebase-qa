from typing import TypedDict

class QueryState(TypedDict):
      question: str
      repo_id: str
      question_embedding: list[float]
      retrieved_chunks: list[dict]   
      reranked_chunks: list[dict] 
      answer: str


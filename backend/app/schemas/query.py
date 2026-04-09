from pydantic import BaseModel


class QueryRequest(BaseModel):
    question: str
    repo_id: str


class Source(BaseModel):
    file_path: str
    name: str | None
    start_line: int
    end_line: int


class QueryResponse(BaseModel):
    answer: str
    sources: list[Source]

from pydantic import BaseModel


class IngestRequest(BaseModel):
    repo_url: str


class IngestResponse(BaseModel):
    status: str
    message: str
    chunks_stored: int
    repo_id: str | None = None

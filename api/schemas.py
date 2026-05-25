from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str


class IndexStatus(BaseModel):
    exists: bool


class PipelineRequest(BaseModel):
    input_folder: str = Field(..., description="Path to folder containing PDF/TXT files")
    output_path: str = Field("./output.json", description="Where to write output.json")
    rebuild_index: bool = Field(False, description="Force rebuild FAISS index even if one exists")
    filenames: list[str] | None = Field(None, description="If set, only process these filenames from input_folder")


class PipelineResponse(BaseModel):
    total: int
    results: dict


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Semantic search query")
    top_k: int = Field(5, ge=1, le=50, description="Number of results to return")


class SearchResult(BaseModel):
    filename: str
    score: float
    snippet: str


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]


class UploadResponse(BaseModel):
    filename: str
    size: int
    saved_to: str


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, description="Question to ask about the documents")
    top_k: int = Field(3, ge=1, le=10, description="Number of chunks to retrieve as context")


class ChatSource(BaseModel):
    filename: str
    snippet: str
    score: float


class ChatResponse(BaseModel):
    answer: str
    sources: list[ChatSource]

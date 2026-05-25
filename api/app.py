import json
import logging
import re
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile, File, Query
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger(__name__)

from api.schemas import (
    ChatRequest,
    ChatResponse,
    HealthResponse,
    IndexStatus,
    PipelineRequest,
    PipelineResponse,
    SearchRequest,
    SearchResponse,
    UploadResponse,
)

UPLOAD_DIR = Path("documents")
DEFAULT_MODEL = "./bge-base-en-v1.5"


def _preload_models() -> None:
    logger.info("Pre-loading BGE retrieval model...")
    from pipeline.retrieval import preload as preload_retrieval
    preload_retrieval(DEFAULT_MODEL)
    logger.info("BGE model ready. Pre-loading Qwen chat model...")
    from pipeline.qa import preload as preload_qa
    preload_qa()
    logger.info("All models ready.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    _preload_models()
    yield


app = FastAPI(
    title="Document Intelligence API",
    description="REST API for document ingestion, classification, field extraction, and semantic search.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse, tags=["Status"])
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get("/index/status", response_model=IndexStatus, tags=["Status"])
def index_status() -> IndexStatus:
    from pipeline.retrieval import index_exists
    return IndexStatus(exists=index_exists())


@app.post("/pipeline/run", response_model=PipelineResponse, tags=["Pipeline"])
def run_pipeline(req: PipelineRequest) -> PipelineResponse:
    from pipeline.ingestion import ingest_folder
    from pipeline.classifier import classify_documents
    from pipeline.extractor import extract_fields
    from pipeline.retrieval import build_index

    texts = ingest_folder(req.input_folder)
    if req.filenames:
        allowed = set(req.filenames)
        texts = {k: v for k, v in texts.items() if k in allowed}
    if not texts:
        raise HTTPException(
            status_code=422,
            detail=f"No PDF or TXT files found in: {req.input_folder}",
        )

    classifications = classify_documents(texts, model_path=DEFAULT_MODEL)

    results: dict = {}
    for filename, text in texts.items():
        clf = classifications.get(filename, {})
        doc_class = clf.get("class", "Unclassifiable")
        fields = extract_fields(filename, text, doc_class)
        entry: dict = {"class": doc_class}
        entry.update(fields)
        results[filename] = entry

    output_path = Path(req.output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    build_index(texts, model_path=DEFAULT_MODEL, results=results)

    return PipelineResponse(total=len(results), results=results)


@app.get("/results", tags=["Pipeline"])
def get_results(output: str = Query("./output.json", description="Path to output.json")):
    path = Path(output)
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail="No results found. Run the pipeline first with POST /pipeline/run.",
        )
    return json.loads(path.read_text(encoding="utf-8"))


_EXCLUDED_CLASSES = {"Other", "Unclassifiable"}

_MONTH_MAP: dict[str, str] = {
    "january": "01", "february": "02", "march": "03", "april": "04",
    "may": "05", "june": "06", "july": "07", "august": "08",
    "september": "09", "october": "10", "november": "11", "december": "12",
    "jan": "01", "feb": "02", "mar": "03", "apr": "04",
    "jun": "06", "jul": "07", "aug": "08", "sep": "09",
    "oct": "10", "nov": "11", "dec": "12",
}

_DUE_RE = re.compile(
    r"\b(due|payment|pay|owed|outstanding|overdue|unpaid)\b", re.IGNORECASE
)
_ISSUE_RE = re.compile(
    r"\b(issued|billed|billing|invoiced|invoice\s+date|statement\s+date|issue\s+date)\b",
    re.IGNORECASE,
)
_ISO_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


def _detect_month(query: str) -> str | None:
    for word in re.findall(r"[a-z]+", query.lower()):
        if word in _MONTH_MAP:
            return _MONTH_MAP[word]
    return None


def _build_date_filter(
    query: str, output_data: dict[str, dict]
) -> set[str] | None:
    """Return filenames whose date fields match the query.

    Supports two modes:
    - ISO dates in query (e.g. "2025-01-04"): exact match per date, intersection of all.
    - Month words (e.g. "January"): month-tag match, union across fields.

    Returns None when no date signal detected (no filter applied).
    Returns empty set when dates detected but no documents match.
    """
    # ── ISO date mode ────────────────────────────────────────────────────────
    iso_dates = _ISO_DATE_RE.findall(query)
    if iso_dates:
        # For each ISO date in the query, find docs that have it in any date field.
        # Intersect across all dates — doc must match ALL specified dates.
        per_date_sets: list[set[str]] = []
        for iso_date in iso_dates:
            matched: set[str] = set()
            for filename, data in output_data.items():
                for field in ("issue_date", "due_date"):
                    if iso_date in str(data.get(field) or ""):
                        matched.add(filename)
                        break
            per_date_sets.append(matched)
        result = per_date_sets[0]
        for s in per_date_sets[1:]:
            result = result & s
        return result  # empty set if nothing matched

    # ── Month-word mode ──────────────────────────────────────────────────────
    month = _detect_month(query)
    if not month:
        return None

    month_tag = f"-{month}-"
    is_due = bool(_DUE_RE.search(query))
    is_issue = bool(_ISSUE_RE.search(query))

    if is_due and not is_issue:
        fields = ["due_date"]
    elif is_issue and not is_due:
        fields = ["issue_date"]
    else:
        fields = ["due_date", "issue_date"]

    matched = set()
    for filename, data in output_data.items():
        for field in fields:
            if month_tag in str(data.get(field) or ""):
                matched.add(filename)
                break

    return matched


@app.post("/search", response_model=SearchResponse, tags=["Search"])
def search(req: SearchRequest) -> SearchResponse:
    from pipeline.retrieval import search as retrieval_search, index_exists

    if not index_exists():
        raise HTTPException(
            status_code=404,
            detail="No search index found. Run the pipeline first with POST /pipeline/run.",
        )

    # Load output.json once — used for both class exclusion and date filtering
    output_path = Path("./output.json")
    output_data: dict[str, dict] = {}
    if output_path.exists():
        output_data = json.loads(output_path.read_text(encoding="utf-8"))

    # Remove excluded classes from the candidate pool
    searchable = {
        fn: data for fn, data in output_data.items()
        if str(data.get("class", "")) not in _EXCLUDED_CLASSES
    }

    # Structured date filter — None means "no month detected, search everything"
    allowed = _build_date_filter(req.query, searchable)

    # When a month is detected but no docs match → return empty immediately
    if allowed is not None and len(allowed) == 0:
        return SearchResponse(query=req.query, results=[])

    # If no date filter, restrict to searchable (non-excluded) filenames
    if allowed is None and searchable:
        allowed = set(searchable.keys())

    hits = retrieval_search(
        req.query,
        top_k=req.top_k,
        model_path=DEFAULT_MODEL,
        allowed_filenames=allowed if allowed else None,
    )

    return SearchResponse(query=req.query, results=hits)


@app.post("/documents/upload", response_model=UploadResponse, tags=["Documents"])
async def upload_document(file: UploadFile = File(...)) -> UploadResponse:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".pdf", ".txt"}:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{suffix}'. Only .pdf and .txt are accepted.",
        )

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    dest = UPLOAD_DIR / (file.filename or "upload")
    content = await file.read()
    dest.write_bytes(content)

    return UploadResponse(
        filename=file.filename or "upload",
        size=len(content),
        saved_to=str(dest),
    )


@app.post("/chat", response_model=ChatResponse, tags=["Chat"])
def chat(req: ChatRequest) -> ChatResponse:
    from pipeline.qa import answer

    # Apply the same date filter + class exclusion as /search
    output_path = Path("./output.json")
    output_data: dict[str, dict] = {}
    if output_path.exists():
        output_data = json.loads(output_path.read_text(encoding="utf-8"))

    searchable = {
        fn: data for fn, data in output_data.items()
        if str(data.get("class", "")) not in _EXCLUDED_CLASSES
    }

    allowed = _build_date_filter(req.question, searchable)
    date_filter_active = _detect_month(req.question) is not None
    if allowed is None and searchable:
        allowed = set(searchable.keys())

    # When date filter is active all retrieved docs are relevant → show all to LLM.
    # For specific lookups (no month), only feed top-1 to LLM to avoid hallucination.
    llm_context_limit = req.top_k if date_filter_active else 1

    result = answer(
        req.question,
        top_k=req.top_k,
        allowed_filenames=allowed if allowed else None,
        llm_context_limit=llm_context_limit,
    )
    return ChatResponse(answer=result["answer"], sources=result["sources"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.app:app", host="0.0.0.0", port=8000, reload=True)

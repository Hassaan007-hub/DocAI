# Local AI Document Intelligence Pipeline

A fully local, offline-capable document intelligence system that ingests PDF and TXT files, classifies each document, extracts structured fields, and exposes semantic search and a chatbot — all via a REST API and a React frontend. No paid or hosted AI APIs required.

---

## Project Structure

```
.
├── main.py                    # CLI entry point (pipeline + search)
├── api/
│   ├── app.py                 # FastAPI application (routes, date filter, lifespan)
│   └── schemas.py             # Pydantic request/response models
├── pipeline/
│   ├── ingestion.py           # PDF/TXT → clean text
│   ├── classifier.py          # Zero-shot classification via sentence embeddings
│   ├── extractor.py           # Per-class regex field extraction
│   ├── retrieval.py           # FAISS index + hybrid BM25/semantic search
│   └── qa.py                  # Chatbot (Qwen2.5 + structured answer bypass)
├── frontend/                  # React + Vite + shadcn/ui frontend
├── documents/                 # Uploaded documents (tracked by git as test set)
├── output.json                # Extracted fields for all processed documents
├── bge-base-en-v1.5/          # Embedding model (download separately, not in git)
├── Qwen2.5-0.5B-Instruct/     # LLM (download separately, not in git)
├── models/                    # FAISS index + chunk metadata (generated at runtime)
└── pyproject.toml
```

---

## Setup

### 1. Install Python dependencies

```bash
git clone <repo>
cd Structure_Extract_and_Chatbot

# Install uv if you don't have it
pip install uv

# Install all dependencies
uv sync
```

### 2. Install frontend dependencies

```bash
cd frontend
npm install
```

### 3. Download the models

**Embedding model (BGE)** — used for document classification and semantic search:

> Download from: [BAAI/bge-base-en-v1.5](https://huggingface.co/BAAI/bge-base-en-v1.5)

Place it in `./bge-base-en-v1.5/` at the project root. Or download automatically via Python (requires internet once):

```bash
uv run python -c "from sentence_transformers import SentenceTransformer; m = SentenceTransformer('BAAI/bge-base-en-v1.5'); m.save('./bge-base-en-v1.5')"
```

**LLM (Qwen2.5)** — used by the chatbot for open-ended questions:

> Download from: [Qwen/Qwen2.5-0.5B-Instruct](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct)

Place it in `./Qwen2.5-0.5B-Instruct/` at the project root. Or download automatically:

```bash
uv run python -c "from transformers import AutoModelForCausalLM, AutoTokenizer; t = AutoTokenizer.from_pretrained('Qwen/Qwen2.5-0.5B-Instruct'); m = AutoModelForCausalLM.from_pretrained('Qwen/Qwen2.5-0.5B-Instruct'); t.save_pretrained('./Qwen2.5-0.5B-Instruct'); m.save_pretrained('./Qwen2.5-0.5B-Instruct')"
```

After downloading, both models are used fully offline — no internet connection required at runtime.

---

## Running the Application

### Start the API server

```bash
uv run uvicorn api.app:app --host 0.0.0.0 --port 8000
```

Both models (BGE + Qwen) are preloaded at startup so the first request has no cold-start delay.

### Start the frontend

```bash
cd frontend
npm run dev
```

Open [http://localhost:5173](http://localhost:5173) in your browser.

### CLI (alternative, no API needed)

```bash
# Run pipeline on a folder
uv run python main.py --input ./documents

# Semantic search
uv run python main.py --search "payments due in January 2025"
uv run python main.py --search "candidates with Python experience" --top-k 3
```

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `GET` | `/index/status` | Check if FAISS index exists |
| `POST` | `/documents/upload` | Upload a PDF or TXT file |
| `POST` | `/pipeline/run` | Run full pipeline on uploaded files |
| `GET` | `/results` | Fetch `output.json` contents |
| `POST` | `/search` | Semantic + keyword search |
| `POST` | `/chat` | Ask a question about the documents |

---

## Output Format

`output.json` maps each filename to its classification and extracted fields:

```json
{
  "invoice_1.pdf": {
    "class": "Invoice",
    "invoice_number": "INV-1234",
    "issue_date": "2025-01-15",
    "due_date": "2025-02-01",
    "company": "ACME Ltd.",
    "total_amount": 350.50
  },
  "resume_john.pdf": {
    "class": "Resume",
    "name": "John Doe",
    "email": "john@example.com",
    "phone": "123-456-7890",
    "experience_years": 5
  },
  "electric_bill.pdf": {
    "class": "Utility Bill",
    "account_number": "ACC-987654",
    "issue_date": "2025-01-01",
    "due_date": "2025-01-20",
    "usage_kwh": 450.0,
    "amount_due": 89.50
  }
}
```

All fields default to `null` when not found.

---

## Sample Documents

The `documents/` folder contains 23 sample files (PDFs and TXT) for testing the pipeline end-to-end:

```
documents/
├── doc_1.pdf  – doc_3.pdf   (Invoices)
├── doc_7.pdf  – doc_12.pdf  (Resumes, Utility Bills, mixed)
├── doc_16.pdf – doc_20.pdf  (mixed classes)
├── doc_4.txt  – doc_6.txt   (TXT documents)
└── doc_13.txt – doc_23.txt  (TXT documents)
```

Upload any of these via the frontend or point the CLI at `./documents` to try the pipeline immediately after setup.

---

## Architecture

### 1. Ingestion

`pdfminer.six` is the primary PDF parser, chosen for its superior layout preservation in multi-column documents. When it fails (encrypted, malformed, or unusual PDFs), `pypdf` is tried as a fallback. TXT files are read directly. All extracted text is normalized (whitespace collapsed, encoding issues handled) before being passed downstream.

### 2. Zero-Shot Document Classification

The classifier uses no labeled training data or fine-tuning. It works by:

1. Embedding the first 1,000 characters of each document with BGE.
2. Embedding multiple natural-language descriptions for each document class (4 content-style variants per class, e.g. "This is a commercial invoice with line items, billing address, and a total amount due").
3. Computing cosine similarity between the document embedding and each description embedding.
4. Taking the maximum score across the 4 variants per class and picking the winning class.

Using multiple description variants per class significantly improves discriminability compared to a single generic description. A threshold of 0.20 catches blank or truly ambiguous documents and labels them `Unclassifiable` rather than forcing a wrong guess.

**Why BGE over MiniLM:** `BAAI/bge-base-en-v1.5` was tested against `all-MiniLM-L6-v2` on the actual document corpus and produced 26/26 correct classifications (average confidence 0.66) versus lower accuracy with MiniLM.

### 3. Regex Field Extraction

Structured fields (invoice numbers, dates, amounts, emails, phone numbers) follow predictable patterns. Regex is used instead of an LLM for extraction because:

- It is deterministic and fast (no inference cost per document).
- The fields follow consistent formatting conventions across the document corpus.
- LLMs of this size hallucinate field values or confuse field types when asked to enumerate all fields.

The regexes are specifically tuned for two-column PDF layouts where `pdfminer` splits labels and values onto separate lines (e.g., `Invoice No:\n\nINV-8821`). All patterns use `[ \t]*` between label and value — never `\s*` — to prevent cross-line false matches where the regex skips the value and captures the next label on the page instead.

### 4. Hybrid BM25 + Semantic Search

Search combines two complementary signals:

- **FAISS (semantic):** The query and all document chunks are embedded with BGE. FAISS `IndexFlatIP` performs exact cosine similarity search (L2-normalized vectors, inner-product = cosine). Captures meaning even when the user's words don't appear literally.
- **BM25 Okapi (keyword):** Classical term-frequency ranking. Excels at exact matches like invoice numbers, phone numbers, or account IDs that semantic models may not distinguish well.

**Fusion:** Scores are combined with equal weight (`0.5 × FAISS_cosine + 0.5 × BM25_normalized`). BM25 raw scores are normalized to [0, 1] with a floor of 1.0 — this prevents a very small BM25 maximum (when all documents score nearly equally low on a purely semantic query) from inflating into an artificial [0, 1] range that would swamp the FAISS signal.

**Why not Reciprocal Rank Fusion (RRF):** RRF uses only rank position, not score magnitude. When BM25 scores one document at 8.99 and all others at 0.00 (an exact ID match), documents with zero BM25 score still get sequential BM25 ranks, allowing a high-FAISS / zero-BM25 document to beat the exact-match winner. Score-based fusion preserves magnitude: the exact-match document gets `bm25_norm ≈ 1.0`, dominating regardless of its FAISS rank.

**Token normalization:** BM25 tokenization (`text.lower().split()`) keeps punctuation attached to tokens. A corpus token like `inv-bv-0055.` (trailing period) never matches a query token like `#INV-BV-0055` (leading `#`). Both corpus and query tokens are stripped of leading/trailing non-alphanumeric characters before scoring.

**Chunking:** Documents are split into 200-word chunks with 50-word overlap before embedding. Long documents are covered end-to-end; the overlap prevents relevant passages at chunk boundaries from being missed. Results are deduplicated by filename (highest-scoring chunk per file).

**Metadata-enriched index:** For each document, a synthetic natural-language chunk is prepended to the index summarizing the extracted fields (invoice number, dates, amounts, etc.). Dates are indexed in both ISO format (`2025-01-15`) and human-readable form (`January 15, 2025`) so queries using either form match correctly.

### 5. Date-Aware Query Filtering

Before calling the search index, the API parses the query for date signals:

- **ISO dates** (`2025-01-04`): exact match against `issue_date` / `due_date` fields in `output.json`. Intersection when multiple dates appear in the query.
- **Month words** (`January`, `Jan`): matched against month substring (`-01-`) in date fields. Intent detection (`due`, `payment`, `owed` → filter `due_date` only; `issued`, `billed` → filter `issue_date` only; ambiguous → both fields).

The resulting filename set is passed to FAISS as `allowed_filenames`, so the vector search only scores documents that actually match the date constraint. When a month is detected but no documents match, the API returns empty immediately without touching the index.

### 6. Chatbot with Structured Answer Bypass

The chatbot uses `Qwen2.5-0.5B-Instruct` (a 500M-parameter causal LM) for open-ended question answering. However, for questions about classified documents (Invoice, Resume, Utility Bill), the LLM is bypassed entirely:

1. The top retrieved document is looked up in `output.json`.
2. The relevant fields for that document class are formatted into a structured block.
3. That block is returned directly as the answer — no token generation.

This avoids the hallucination problem that small LLMs exhibit when asked to enumerate document fields (wrong field names, fabricated values, confusion between Invoice and Utility Bill fields). The LLM is only called when no structured data is available — for `Other`-class documents or open-ended reasoning questions.

### 7. Eager Model Loading

Both models (BGE and Qwen) are loaded once at server startup via FastAPI's `lifespan` context manager. Each model is cached in a module-level singleton protected by a `threading.Lock()`, so concurrent requests share the same model instance without race conditions. This eliminates per-request cold-start latency (BGE load: ~2s, Qwen load: ~5s on CPU).

---

## Libraries Used

| Library | Role |
|---|---|
| `pdfminer.six` | Primary PDF text extraction (best multi-column layout handling) |
| `pypdf` | Fallback PDF extraction for edge cases |
| `sentence-transformers` | BGE embedding model — classification + search |
| `faiss-cpu` | Exact cosine similarity search over document chunks |
| `rank-bm25` | BM25 Okapi keyword scoring |
| `transformers` + `torch` | Qwen2.5 LLM inference for chatbot |
| `fastapi` + `uvicorn` | REST API server |
| `rich` | Terminal tables and progress display (CLI mode) |




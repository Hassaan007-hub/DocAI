import json
import logging
import threading
import numpy as np
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


def _date_to_human(date_str: str | None) -> str | None:
    """Convert YYYY-MM-DD to 'Month DD, YYYY' for natural-language indexing."""
    if not date_str:
        return None
    try:
        return datetime.strptime(str(date_str), "%Y-%m-%d").strftime("%B %d, %Y")
    except ValueError:
        return str(date_str)


def _make_metadata_chunk(filename: str, data: dict) -> str:
    """Build a natural-language summary of extracted fields for a document.

    Includes dates in both human ('January 15, 2025') and ISO ('2025-01-15')
    form so semantic search can match either format.
    """
    doc_class = str(data.get("class", ""))
    parts: list[str] = [f"Document: {filename}."]

    if doc_class == "Invoice":
        if data.get("invoice_number"):
            parts.append(f"Invoice number: {data['invoice_number']}.")
        if data.get("company"):
            parts.append(f"Company: {data['company']}.")
        if data.get("issue_date"):
            human = _date_to_human(str(data["issue_date"]))
            parts.append(f"Issued on {human} ({data['issue_date']}).")
        if data.get("due_date"):
            human = _date_to_human(str(data["due_date"]))
            parts.append(
                f"Payment is due in {datetime.strptime(str(data['due_date']), '%Y-%m-%d').strftime('%B %Y')}."
                f" Due date: {human} ({data['due_date']})."
            )
        if data.get("total_amount") is not None:
            parts.append(f"Total amount: ${data['total_amount']}.")

    elif doc_class == "Resume":
        if data.get("name"):
            parts.append(f"Resume of {data['name']}.")
        if data.get("email"):
            parts.append(f"Email: {data['email']}.")
        if data.get("phone"):
            parts.append(f"Phone: {data['phone']}.")
        if data.get("experience_years") is not None:
            parts.append(f"Experience: {data['experience_years']} years.")

    elif doc_class == "Utility Bill":
        if data.get("account_number"):
            parts.append(f"Account number: {data['account_number']}.")
        if data.get("issue_date"):
            human = _date_to_human(str(data["issue_date"]))
            parts.append(f"Issued on {human} ({data['issue_date']}).")
        if data.get("due_date"):
            human = _date_to_human(str(data["due_date"]))
            parts.append(
                f"Payment is due in {datetime.strptime(str(data['due_date']), '%Y-%m-%d').strftime('%B %Y')}."
                f" Due date: {human} ({data['due_date']})."
            )
        if data.get("usage_kwh") is not None:
            parts.append(f"Usage: {data['usage_kwh']} kWh.")
        if data.get("amount_due") is not None:
            parts.append(f"Amount due: ${data['amount_due']}.")

    return " ".join(parts)

_INDEX_PATH = Path("models") / "faiss.index"
_META_PATH = Path("models") / "chunk_metadata.json"
_CHUNK_WORDS = 200
_OVERLAP_WORDS = 50


def _chunk_text(text: str) -> list[str]:
    words = text.split()
    if not words:
        return []
    step = _CHUNK_WORDS - _OVERLAP_WORDS
    chunks = []
    i = 0
    while i < len(words):
        chunks.append(" ".join(words[i : i + _CHUNK_WORDS]))
        i += step
    return chunks


def _load_model(model_path: str = "./bge-base-en-v1.5"):
    from sentence_transformers import SentenceTransformer
    path = Path(model_path)
    if not path.exists():
        raise FileNotFoundError(f"Model not found at: {model_path}")
    return SentenceTransformer(str(path), local_files_only=True)


_bge_lock = threading.Lock()
_bge_model = None
_bge_model_path: str | None = None


def get_model(model_path: str = "./bge-base-en-v1.5"):
    """Return a cached SentenceTransformer instance, loading it once on first call."""
    global _bge_model, _bge_model_path
    with _bge_lock:
        if _bge_model is None or _bge_model_path != model_path:
            _bge_model = _load_model(model_path)
            _bge_model_path = model_path
    return _bge_model


def preload(model_path: str = "./bge-base-en-v1.5") -> None:
    get_model(model_path)


def _normalize(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1, norms)
    return vectors / norms


def build_index(
    texts: dict[str, str],
    model_path: str = "./bge-base-en-v1.5",
    index_path: Path | None = None,
    meta_path: Path | None = None,
    results: dict | None = None,
) -> None:
    """Chunk, embed, and persist the FAISS index from all document texts.

    If `results` (the extracted-fields dict from output.json) is provided, a
    synthetic metadata chunk is prepended for each document.  The chunk contains
    dates in both ISO ('2025-01-15') and human ('January 15, 2025') form so
    natural-language queries like 'payments due in January' match correctly.
    """
    import faiss

    index_path = index_path or _INDEX_PATH
    meta_path = meta_path or _META_PATH
    index_path.parent.mkdir(parents=True, exist_ok=True)

    model = get_model(model_path)

    all_chunks: list[str] = []
    metadata: list[dict] = []

    for filename, text in texts.items():
        # Prepend structured metadata chunk when extracted fields are available
        if results and filename in results:
            meta_text = _make_metadata_chunk(filename, results[filename])
            all_chunks.append(meta_text)
            metadata.append({"filename": filename, "chunk_index": -1, "chunk_text": meta_text[:300]})

        for i, chunk in enumerate(_chunk_text(text)):
            all_chunks.append(chunk)
            metadata.append({"filename": filename, "chunk_index": i, "chunk_text": chunk})

    if not all_chunks:
        logger.warning("No text chunks to index.")
        return

    logger.info("Embedding %d chunks for FAISS index...", len(all_chunks))
    embeddings = model.encode(
        all_chunks, convert_to_numpy=True, show_progress_bar=False, batch_size=64
    )
    embeddings = _normalize(embeddings.astype(np.float32))

    index = faiss.IndexFlatIP(embeddings.shape[1])
    index.add(embeddings)

    faiss.write_index(index, str(index_path))
    meta_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    logger.info("FAISS index saved: %d vectors → %s", index.ntotal, index_path)


def search(
    query: str,
    top_k: int = 5,
    model_path: str = "./bge-base-en-v1.5",
    index_path: Path | None = None,
    meta_path: Path | None = None,
    allowed_filenames: set[str] | None = None,
) -> list[dict]:
    """
    Hybrid BM25 + semantic search fused with Reciprocal Rank Fusion (RRF).

    Returns list of {"filename", "score", "snippet"}, deduplicated by filename.
    Scores are normalized to [0, 1] relative to the top result.

    If `allowed_filenames` is provided only results from that set are returned.
    """
    import faiss
    from rank_bm25 import BM25Okapi

    index_path = index_path or _INDEX_PATH
    meta_path = meta_path or _META_PATH

    if not index_path.exists() or not meta_path.exists():
        return []

    index = faiss.read_index(str(index_path))
    metadata: list[dict] = json.loads(meta_path.read_text(encoding="utf-8"))
    n_total = len(metadata)

    # ── Semantic: embed query, search all vectors ─────────────────────────
    model = get_model(model_path)
    q_emb = model.encode([query], convert_to_numpy=True, show_progress_bar=False)
    q_emb = _normalize(q_emb.astype(np.float32))

    faiss_scores, faiss_indices = index.search(q_emb, index.ntotal)
    # Map chunk index → cosine similarity score
    faiss_score_map: dict[int, float] = {
        int(idx): float(score)
        for score, idx in zip(faiss_scores[0], faiss_indices[0])
        if 0 <= idx < n_total
    }

    # ── BM25: tokenize corpus and query, score all chunks ─────────────────
    # Normalize tokens by stripping leading/trailing punctuation so that
    # '#INV-BV-0055' matches 'inv-bv-0055.' in the corpus.
    import re as _re

    def _normalize_tokens(text: str) -> list[str]:
        return [
            t for t in (
                _re.sub(r"^[^a-z0-9]+|[^a-z0-9]+$", "", tok)
                for tok in text.lower().split()
            ) if t
        ]

    tokenized_corpus = [_normalize_tokens(m["chunk_text"]) for m in metadata]
    bm25 = BM25Okapi(tokenized_corpus)
    bm25_raw = bm25.get_scores(_normalize_tokens(query))

    # ── Score-based hybrid fusion ─────────────────────────────────────────
    # Normalize BM25 scores to [0, 1]. A floor of 1.0 prevents a tiny BM25
    # max (when all docs score equally low) from inflating to 1.0 and
    # swamping the FAISS signal on purely semantic queries.
    bm25_max = float(max(bm25_raw)) if max(bm25_raw) > 0 else 1.0
    _BM25_FLOOR = 1.0
    bm25_norm = [bm25_raw[i] / max(bm25_max, _BM25_FLOOR) for i in range(n_total)]

    # Equal weight between semantic (FAISS cosine) and keyword (BM25) scores.
    # When BM25 has an exact-match winner (e.g. a phone number or invoice ID),
    # bm25_norm[winner] ≈ 1.0 while all others ≈ 0.0, so BM25 dominates.
    # For semantic-only queries, BM25 contributions are uniformly small and
    # FAISS cosine similarity governs ranking.
    _ALPHA = 0.5
    hybrid: dict[int, float] = {
        i: (1 - _ALPHA) * faiss_score_map.get(i, 0.0) + _ALPHA * bm25_norm[i]
        for i in range(n_total)
    }

    # ── Deduplicate by filename, apply allowed_filenames filter ───────────
    seen: dict[str, dict] = {}
    for i, score in sorted(hybrid.items(), key=lambda x: x[1], reverse=True):
        meta = metadata[i]
        filename = meta["filename"]
        if allowed_filenames is not None and filename not in allowed_filenames:
            continue
        if filename not in seen or score > seen[filename]["score"]:
            seen[filename] = {
                "filename": filename,
                "score": score,
                "snippet": meta["chunk_text"][:300],
            }

    results = sorted(seen.values(), key=lambda x: x["score"], reverse=True)[:top_k]

    # Normalize scores to [0, 1] relative to top result so the frontend bar is meaningful
    if results:
        max_score = results[0]["score"]
        if max_score > 0:
            for r in results:
                r["score"] = round(r["score"] / max_score, 4)

    return results


def index_exists(
    index_path: Path | None = None,
    meta_path: Path | None = None,
) -> bool:
    index_path = index_path or _INDEX_PATH
    meta_path = meta_path or _META_PATH
    return index_path.exists() and meta_path.exists()

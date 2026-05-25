import logging
import numpy as np
from pathlib import Path

logger = logging.getLogger(__name__)

# Example-content labels: short snippets that look like actual document text.
# all-MiniLM-L6-v2 is a semantic similarity model — it scores best when label text
# resembles the document text style rather than meta-descriptions about the document.
LABEL_DESCRIPTIONS: dict[str, list[str]] = {
    "Invoice": [
        "INVOICE Invoice Number INV-1234 Bill To Company Name Total Amount Due $500.00",
        "Tax Invoice commercial vendor billing address Line items Subtotal Tax Grand Total Payment Due",
        "Invoice Date Due Date Item Description Quantity Unit Price Total Amount goods services",
    ],
    "Resume": [
        "Work Experience Software Engineer Company Name years of experience Skills Python Java",
        "PROFESSIONAL SUMMARY Senior Developer education B.Sc Computer Science employment history",
        "Resume Curriculum Vitae Name email phone LinkedIn portfolio job title university degree skills",
        "Data Scientist machine learning WORK HISTORY M.S. Statistics university publications research",
    ],
    "Utility Bill": [
        "ELECTRICITY BILL TAX INVOICE Account Number meter reading Usage kWh billing period Amount Due",
        "Utility Statement Gas Water Electric Supply Company consumption units payment due date",
        "Account Summary electric supply company Previous balance Current charges Total amount due",
    ],
    "Other": [
        "SERVICE AGREEMENT This Agreement entered into between Company A and Company B terms conditions",
        "MEDICAL REPORT Patient diagnosis treatment hospital department physician clinical findings",
        "Dear Sir Madam This letter formal notice contract agreement signed parties obligations",
    ],
    "Unclassifiable": [
        "asdf jkl qwerty fragment corrupted random text gibberish lorem ipsum Page of",
        "ERROR blank page unreadable content missing data corrupted file",
        "unknown document no recognizable content random characters symbols",
    ],
}

_UNCLASSIFIABLE_THRESHOLD = 0.20
_TEXT_TRUNCATE = 1000


def _load_model(model_path: str = "./bge-base-en-v1.5"):
    from sentence_transformers import SentenceTransformer
    path = Path(model_path)
    if not path.exists():
        raise FileNotFoundError(f"Model not found at: {model_path}")
    return SentenceTransformer(str(path), local_files_only=True)


def _normalize(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1, norms)
    return vectors / norms


def _embed_labels(model) -> dict[str, np.ndarray]:
    """Returns {label: embeddings_matrix} — all variant embeddings per label."""
    label_embeddings: dict[str, np.ndarray] = {}
    for label, descriptions in LABEL_DESCRIPTIONS.items():
        embs = model.encode(descriptions, convert_to_numpy=True, show_progress_bar=False)
        label_embeddings[label] = _normalize(embs)  # (n_variants, dim)
    return label_embeddings


def classify_documents(
    texts: dict[str, str],
    model_path: str = "./bge-base-en-v1.5",
) -> dict[str, dict]:
    """Returns {filename: {"class": label, "confidence": float}}"""
    if not texts:
        return {}

    model = _load_model(model_path)
    label_embeddings = _embed_labels(model)
    labels = list(label_embeddings.keys())

    results: dict[str, dict] = {}

    for filename, text in texts.items():
        try:
            snippet = text[:_TEXT_TRUNCATE]
            doc_emb = model.encode([snippet], convert_to_numpy=True, show_progress_bar=False)
            doc_emb = _normalize(doc_emb)[0]  # (dim,)

            # Max similarity across all variants for each label
            scores = np.array([
                float((label_embeddings[label] @ doc_emb).max())
                for label in labels
            ])
            best_idx = int(np.argmax(scores))
            best_score = float(scores[best_idx])
            best_label = labels[best_idx]

            if best_score < _UNCLASSIFIABLE_THRESHOLD:
                best_label = "Unclassifiable"
                best_score = float(scores[labels.index("Unclassifiable")])

            results[filename] = {"class": best_label, "confidence": round(best_score, 4)}

        except Exception as e:
            logger.error("Failed to classify %s: %s", filename, e)
            results[filename] = {"class": "Unclassifiable", "confidence": 0.0}

    return results

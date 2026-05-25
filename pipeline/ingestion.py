import logging
import unicodedata
import re
from pathlib import Path

logger = logging.getLogger(__name__)

_UNREADABLE = "[UNREADABLE - possible scanned image]"
_MIN_PDF_CHARS = 50


def _extract_pdf(path: Path) -> str:
    text = ""

    try:
        from pdfminer.high_level import extract_text as pdfminer_extract
        text = pdfminer_extract(str(path)) or ""
    except Exception as e:
        logger.debug("pdfminer failed on %s: %s", path.name, e)

    if len(text.strip()) < _MIN_PDF_CHARS:
        try:
            from pypdf import PdfReader
            reader = PdfReader(str(path))
            text = "\n".join(
                page.extract_text() or "" for page in reader.pages
            )
        except Exception as e:
            logger.debug("pypdf failed on %s: %s", path.name, e)

    if len(text.strip()) < _MIN_PDF_CHARS:
        logger.warning("Unreadable PDF (likely scanned image): %s", path.name)
        return _UNREADABLE

    return text


def _clean_text(raw: str) -> str:
    text = unicodedata.normalize("NFKC", raw)
    # strip control characters, keep \n and \t
    text = re.sub(r"[^\S\n\t]+", " ", text)
    text = re.sub(r"[^\x09\x0a\x20-\x7e\x80-\xff]", "", text)
    # collapse 3+ newlines to 2
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def ingest_folder(folder_path: str) -> dict[str, str]:
    """Return {filename: clean_text} for all PDFs and TXTs in folder_path."""
    root = Path(folder_path)

    if not root.exists() or not root.is_dir():
        logger.error("Folder not found: %s", folder_path)
        return {}

    results: dict[str, str] = {}

    for file in sorted(root.iterdir()):
        if not file.is_file():
            continue
        suffix = file.suffix.lower()
        if suffix not in {".pdf", ".txt"}:
            continue

        try:
            if suffix == ".pdf":
                raw = _extract_pdf(file)
            else:
                try:
                    raw = file.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    raw = file.read_text(encoding="latin-1")

            results[file.name] = _clean_text(raw)

        except Exception as e:
            logger.error("Failed to ingest %s: %s", file.name, e)

    return results

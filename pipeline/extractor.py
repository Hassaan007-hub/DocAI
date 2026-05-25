import re
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


# ── Shared helpers ────────────────────────────────────────────────────────────

def _to_float(s: str | None) -> float | None:
    if not s:
        return None
    cleaned = re.sub(r"[£$€,\s]|Rs\.?", "", s)
    try:
        return float(cleaned)
    except ValueError:
        return None


def _try_parse_date(s: str) -> str | None:
    s = s.strip()
    for fmt in (
        "%d %B %Y", "%B %d, %Y",
        "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y",
        "%d %b %Y", "%b %d, %Y",
    ):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None


def _extract_date(text: str, label_hints: list[str] | None = None) -> str | None:
    """Return YYYY-MM-DD for the first recognisable date near any of label_hints."""
    hints = label_hints or [
        r"Invoice\s+Date", r"Issue\s+Date", r"Statement\s+Date",
        r"Bill\s+Date", r"Issued", r"Date",
    ]
    for hint in hints:
        # Allow optional newlines between label colon and value (PDF two-column layout
        # emits "Label:\n\nValue" rather than "Label: Value").
        m = re.search(hint + r"[ \t]*:[ \t]*\n*[ \t]*([^\n]{5,40})", text, re.IGNORECASE)
        if m:
            d = _try_parse_date(m.group(1))
            if d:
                return d

    # Fallback: first date-like string anywhere in the document
    for pattern in [
        r"\b(\d{1,2}\s+[A-Za-z]+\s+\d{4})\b",
        r"\b([A-Za-z]+\s+\d{1,2},\s+\d{4})\b",
        r"\b(\d{4}-\d{2}-\d{2})\b",
        r"\b(\d{1,2}/\d{1,2}/\d{4})\b",
    ]:
        for m in re.finditer(pattern, text):
            d = _try_parse_date(m.group(1))
            if d:
                return d
    return None


# ── Invoice extractors ────────────────────────────────────────────────────────

_LABEL_WORDS = frozenset({
    "date", "due", "payment", "customer", "client", "ref", "order",
    "description", "qty", "quantity", "amount", "tax",
})


def _invoice_number(text: str) -> str | None:
    # Same-line match only — separator must not cross newlines
    m = re.search(
        r"Invoice\s*(?:Number|No\.?|#)\s*:[ \t]*([\w-]+)",
        text, re.IGNORECASE,
    )
    if m and m.group(1).lower() not in _LABEL_WORDS:
        return m.group(1).strip()
    # Fallback: INV-style number anywhere in the document
    m = re.search(r"\b(INV[-/#]?[\w-]*\d+)\b", text, re.IGNORECASE)
    return m.group(1).strip() if m else None


_COMPANY_SKIP = frozenset({
    "invoice", "tax", "receipt", "date", "due", "payment", "bill",
    "statement", "from", "to", "billed", "number", "total",
    "subtotal", "grand", "description", "quantity", "qty", "rate",
    "amount", "freelance", "ref", "phone", "email", "address",
    "tel", "vat", "fax", "customer", "client", "attn", "attention",
    "dear", "sir", "madam",
})


def _invoice_company(text: str) -> str | None:
    for raw_line in text.split("\n"):
        line = raw_line.strip()
        if not line or not line[0].isalpha():
            continue
        words_lower = re.findall(r"[a-z]+", line.lower())
        if any(w in _COMPANY_SKIP for w in words_lower):
            continue
        if "@" in line or "www." in line.lower():
            continue
        # Skip address lines (digit followed immediately by alphabetic text)
        if re.search(r"\d+\s+[A-Za-z]", line):
            continue
        if len(line.split()) < 2:
            continue
        return line
    return None


def _invoice_total(text: str) -> float | None:
    # For PDFs with two-column layout the amount is separated from the label;
    # search for the label then take the last currency amount that follows it.
    m = re.search(
        r"\b(?:Grand\s+Total|TOTAL\s+DUE|Total\s+Due)\b",
        text, re.IGNORECASE,
    )
    if m:
        amounts = re.findall(r"(?:Rs\.?\s*|[£$€])([\d,]+(?:\.\d+)?)", text[m.start():])
        if amounts:
            return _to_float(amounts[-1])
    # Fallback: "Total: $X" on the same line (text files, no "Sub" prefix)
    m = re.search(r"\bTotal\b\s*:\s*[£$€]?\s*([\d,]+\.?\d*)", text)
    return _to_float(m.group(1)) if m else None


def _extract_invoice(text: str) -> dict:
    return {
        "invoice_number": _invoice_number(text),
        "issue_date": _extract_date(
            text,
            [r"Invoice\s+Date", r"Issue\s+Date", r"Statement\s+Date", r"Issued"],
        ),
        "due_date": _extract_date(
            text,
            [r"Due\s+Date", r"Payment\s+Due", r"Payment\s+Date", r"Due\s+By", r"Pay\s+By"],
        ),
        "company": _invoice_company(text),
        "total_amount": _invoice_total(text),
    }


# ── Resume extractors ─────────────────────────────────────────────────────────

_NAME_SKIP = frozenset({"resume", "cv", "curriculum", "vitae", "profile"})


def _resume_name(text: str) -> str | None:
    for raw_line in text.split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        if any(kw in line.lower() for kw in _NAME_SKIP):
            continue
        words = line.split()
        if len(words) < 2 or len(words) > 4:
            continue
        if any(c.isdigit() for c in line):
            continue
        if not all(w[0].isupper() for w in words if w[0].isalpha()):
            continue
        return line
    return None


def _resume_email(text: str) -> str | None:
    m = re.search(r"[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}", text)
    return m.group(0) if m else None


def _resume_phone(text: str) -> str | None:
    # International format: +XX-XXX-XXX-XXXX or +XX XXXX XXX XXX
    m = re.search(
        r"(\+\d{1,3}[-\s.]?\(?\d{2,4}\)?[-\s.]\d{3,4}[-\s.]\d{3,4})",
        text,
    )
    if m:
        return m.group(1).strip()
    # US/local format: (XXX) XXX-XXXX or XXX-XXX-XXXX
    m = re.search(r"(\(?\d{3}\)?[-\s.]\d{3}[-\s.]\d{4})", text)
    if m:
        return m.group(1).strip()
    # Fallback: (XXX) XXXXXXX — area code + 7 unseparated digits
    m = re.search(r"(\(?\d{3}\)?[-\s.]\d{7})", text)
    return m.group(1).strip() if m else None


def _resume_experience_years(text: str) -> int | None:
    m = re.search(
        r"(?:over\s+|more\s+than\s+)?(\d+)\+?\s+years?\s+of\s+(?:\w+\s+)?experience",
        text, re.IGNORECASE,
    )
    if m:
        return int(m.group(1))
    m = re.search(r"(\d+)\+?\s+years?\s+experience", text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    # e.g. "with 9 years specialising in..." — number stated without the word "experience"
    m = re.search(r"\bwith\s+(\d+)\+?\s+years?\b", text, re.IGNORECASE)
    return int(m.group(1)) if m else None


def _extract_resume(text: str) -> dict:
    return {
        "name": _resume_name(text),
        "email": _resume_email(text),
        "phone": _resume_phone(text),
        "experience_years": _resume_experience_years(text),
    }


# ── Utility Bill extractors ───────────────────────────────────────────────────

def _bill_account_number(text: str) -> str | None:
    # Allow newlines between label and value (PDF two-column layout)
    m = re.search(
        r"Account\s*(?:Number|No\.?|#)?\s*:[ \t]*\n*[ \t]*([\w-]+)",
        text, re.IGNORECASE,
    )
    return m.group(1).strip() if m else None


def _bill_usage_kwh(text: str) -> float | None:
    # Search the "Electric Usage ... Gas" section first (handles PDF column splits)
    m_elec = re.search(r"Electric\s+Usage", text, re.IGNORECASE)
    if m_elec:
        m_gas = re.search(r"Gas\s+(?:Usage|Charges)", text[m_elec.start():], re.IGNORECASE)
        end = m_elec.start() + (m_gas.start() if m_gas else len(text) - m_elec.start())
        m = re.search(r"\b([\d,]+)\s*k[Ww][Hh]\b", text[m_elec.start():end])
        if m:
            return _to_float(m.group(1))

    # "Units Consumed:" label — value may be many lines away in PDF column layout
    m = re.search(r"Units?\s+Consumed\s*:", text, re.IGNORECASE)
    if m:
        km = re.search(r"\b([\d,]+)\s*k[Ww][Hh]\b", text[m.start():m.start() + 500])
        if km:
            return _to_float(km.group(1))

    # "Usage: X kWh" — same line or next line
    m = re.search(r"\bUsage\s*:[ \t]*\n*[ \t]*([\d,]+)\s*k[Ww][Hh]", text, re.IGNORECASE)
    if m:
        return _to_float(m.group(1))
    return None


def _bill_amount_due(text: str) -> float | None:
    # Same two-column strategy as invoice total: find last currency amount after label
    m = re.search(
        r"\b(?:AMOUNT\s+DUE|TOTAL\s+AMOUNT\s+DUE|Total\s+Amount\s+Due)\b",
        text, re.IGNORECASE,
    )
    if not m:
        return None
    amounts = re.findall(r"(?:Rs\.?\s*|[£$€])([\d,]+(?:\.\d+)?)", text[m.start():])
    return _to_float(amounts[-1]) if amounts else None


def _extract_utility_bill(text: str) -> dict:
    return {
        "account_number": _bill_account_number(text),
        "issue_date": _extract_date(
            text,
            [r"Issue\s+Date", r"Statement\s+Date", r"Bill\s+Date", r"Billing\s+Date"],
        ),
        "due_date": _extract_date(
            text,
            [r"Due\s+Date", r"Payment\s+Due", r"Payment\s+Date", r"Due\s+By", r"Pay\s+By"],
        ),
        "usage_kwh": _bill_usage_kwh(text),
        "amount_due": _bill_amount_due(text),
    }


# ── Dispatcher ────────────────────────────────────────────────────────────────

_EXTRACTORS = {
    "Invoice": _extract_invoice,
    "Resume": _extract_resume,
    "Utility Bill": _extract_utility_bill,
}


def extract_fields(filename: str, text: str, doc_class: str) -> dict:
    """Return extracted fields dict based on doc_class. Returns {} for Other/Unclassifiable."""
    extractor = _EXTRACTORS.get(doc_class)
    if extractor is None:
        return {}

    try:
        fields = extractor(text)
        # Replace any extraction failures (exceptions stored as-is) with None
        return {k: v for k, v in fields.items()}
    except Exception as e:
        logger.error("Extraction failed for %s (%s): %s", filename, doc_class, e)
        return {}

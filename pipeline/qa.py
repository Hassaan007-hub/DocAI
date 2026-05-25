from __future__ import annotations

import json
import threading
from pathlib import Path

_OUTPUT_PATH = Path("./output.json")

_CLASS_FIELDS: dict[str, list[str]] = {
    "Invoice":      ["invoice_number", "issue_date", "due_date", "company", "total_amount"],
    "Resume":       ["name", "email", "phone", "experience_years"],
    "Utility Bill": ["account_number", "issue_date", "due_date", "usage_kwh", "amount_due"],
}

_QWEN_PATH = "./Qwen2.5-0.5B-Instruct"

_lock = threading.Lock()
_tokenizer = None
_model = None


def _load_qwen(model_path: str):
    global _tokenizer, _model
    with _lock:
        if _model is None:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer

            _tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
            _model = AutoModelForCausalLM.from_pretrained(
                model_path,
                local_files_only=True,
                dtype=torch.float32,
            )
            _model.eval()
    return _tokenizer, _model


def answer(
    question: str,
    top_k: int = 3,
    qwen_path: str = _QWEN_PATH,
    retrieval_model_path: str = "./bge-base-en-v1.5",
    allowed_filenames: set[str] | None = None,
    llm_context_limit: int = 1,
) -> dict:
    from pipeline.retrieval import index_exists, search

    sources: list[dict] = []
    context_text = ""

    if index_exists():
        hits = search(question, top_k=top_k, model_path=retrieval_model_path,
                      allowed_filenames=allowed_filenames)
        sources = [
            {"filename": h["filename"], "snippet": h["snippet"], "score": h["score"]}
            for h in hits
        ]
        # Load structured output.json so we can build reliable per-class field answers
        output_data: dict = {}
        if _OUTPUT_PATH.exists():
            output_data = json.loads(_OUTPUT_PATH.read_text(encoding="utf-8"))

        # Only feed the top llm_context_limit hits to the LLM
        llm_hits = hits[:llm_context_limit]

        # Build a Python-formatted structured block per document.
        # This is passed to the LLM as ground truth so it never needs to invent fields.
        context_parts: list[str] = []
        structured_blocks: list[str] = []
        for h in llm_hits:
            fname = h["filename"]
            structured = output_data.get(fname, {})
            doc_class = structured.get("class", "Unknown")
            relevant_keys = _CLASS_FIELDS.get(doc_class, [])
            field_lines = [
                f"  {k}: {structured[k]}"
                for k in relevant_keys
                if structured.get(k) is not None
            ]
            block = f"[{fname}] — {doc_class}"
            if field_lines:
                block += "\n" + "\n".join(field_lines)
            context_parts.append(block)
            structured_blocks.append(block)

        context_text = "\n\n".join(context_parts)
        # Pre-built structured answer used when fields are available
        _structured_answer = "\n\n".join(structured_blocks) if structured_blocks else ""

    # If structured fields are available, return them directly — no LLM needed.
    # The LLM is only invoked for open-ended reasoning questions without structured data.
    if _structured_answer:
        return {"answer": _structured_answer, "sources": sources}

    # Fallback: use LLM for questions where no structured data is available
    tokenizer, model = _load_qwen(qwen_path)

    if context_text:
        user_msg = (
            f"Documents:\n\n{context_text}\n\n"
            f"Question: {question}\n\n"
            "Using only the information above, answer the question. Cite each filename."
        )
    else:
        user_msg = (
            f"Question: {question}\n\n"
            "Note: No document index is available. Answer from general knowledge."
        )

    messages = [
        {
            "role": "system",
            "content": (
                "You are a document retrieval assistant. "
                "Answer questions using only the provided document context. "
                "Cite filenames. Be direct and concise."
            ),
        },
        {"role": "user", "content": user_msg},
    ]

    import torch

    text = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )
    inputs = tokenizer([text], return_tensors="pt")

    with torch.no_grad():
        output_ids = model.generate(
            **inputs,
            max_new_tokens=256,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
        )

    new_ids = output_ids[0][inputs["input_ids"].shape[1] :]
    answer_text = tokenizer.decode(new_ids, skip_special_tokens=True).strip()

    return {"answer": answer_text, "sources": sources}


def preload(model_path: str = _QWEN_PATH) -> None:
    _load_qwen(model_path)

import argparse
import json
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

try:
    from rich.console import Console
    from rich.table import Table
    _RICH = True
    console = Console()
except ImportError:
    _RICH = False
    console = None  # type: ignore[assignment]

_DEFAULT_MODEL = "./bge-base-en-v1.5"


def _print(msg: str, style: str = "") -> None:
    if _RICH:
        console.print(f"[{style}]{msg}[/{style}]" if style else msg)
    else:
        print(msg)


def _rule(title: str) -> None:
    if _RICH:
        console.rule(f"[bold blue]{title}[/bold blue]")
    else:
        print(f"\n=== {title} ===")


def _progress(current: int, total: int, message: str) -> None:
    _print(f"[{current}/{total}] {message}", style="dim" if _RICH else "")


def _run_pipeline(args: argparse.Namespace) -> None:
    from pipeline.ingestion import ingest_folder
    from pipeline.classifier import classify_documents
    from pipeline.extractor import extract_fields
    from pipeline.retrieval import build_index, index_exists

    output_path = Path(args.output)

    # ── 1. Ingest ─────────────────────────────────────────────────────────────
    _rule("Step 1/4 — Ingestion")
    texts = ingest_folder(args.input)
    if not texts:
        _print(f"No PDF or TXT files found in: {args.input}", style="bold red")
        sys.exit(1)
    total = len(texts)
    _print(f"Ingested {total} files.", style="green")

    # ── 2. Classify ───────────────────────────────────────────────────────────
    _rule("Step 2/4 — Classification")
    _print(f"[0/{total}] Loading model and classifying all documents...")
    classifications = classify_documents(texts, model_path=_DEFAULT_MODEL)
    _print(f"Classified {total} files.", style="green")

    # ── 3. Extract ────────────────────────────────────────────────────────────
    _rule("Step 3/4 — Field Extraction")
    results: dict[str, dict] = {}
    for i, (filename, text) in enumerate(texts.items(), 1):
        clf = classifications.get(filename, {})
        doc_class = clf.get("class", "Unclassifiable")
        _progress(i, total, f"Extracting {filename}  ({doc_class})")
        fields = extract_fields(filename, text, doc_class)
        entry: dict = {"class": doc_class}
        entry.update(fields)
        results[filename] = entry

    # ── Write output.json ─────────────────────────────────────────────────────
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    _print(f"output.json written -> {output_path}", style="green")

    # ── 4. Build FAISS index ──────────────────────────────────────────────────
    _rule("Step 4/4 — Building Search Index")
    if not index_exists() or args.rebuild_index:
        build_index(texts, model_path=_DEFAULT_MODEL, results=results)
        _print("FAISS index built.", style="green")
    else:
        _print(
            "Index already exists — skipping. Use --rebuild-index to force.",
            style="yellow",
        )

    # ── Summary ───────────────────────────────────────────────────────────────
    _rule("Summary")
    _print_summary(results, classifications)


def _print_summary(results: dict, classifications: dict) -> None:
    if _RICH:
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("File", style="cyan", no_wrap=True)
        table.add_column("Class", style="green")
        table.add_column("Confidence", justify="right")
        table.add_column("Fields Found", justify="right")
        for filename, entry in results.items():
            clf = classifications.get(filename, {})
            conf = f"{clf.get('confidence', 0):.0%}"
            doc_class = entry.get("class", "?")
            n_fields = sum(
                1 for k, v in entry.items() if k != "class" and v is not None
            )
            table.add_row(filename, doc_class, conf, str(n_fields))
        console.print(table)
    else:
        print(f"\n{'File':<42} {'Class':<16} {'Conf':>6} {'Fields':>6}")
        print("-" * 74)
        for filename, entry in results.items():
            clf = classifications.get(filename, {})
            conf = clf.get("confidence", 0)
            doc_class = entry.get("class", "?")
            n_fields = sum(
                1 for k, v in entry.items() if k != "class" and v is not None
            )
            print(f"{filename:<42} {doc_class:<16} {conf:>5.0%} {n_fields:>6}")


def _run_search(args: argparse.Namespace) -> None:
    from pipeline.retrieval import search, index_exists

    if not index_exists():
        _print(
            "No search index found. Run pipeline first with --input <folder>",
            style="bold red",
        )
        sys.exit(1)

    results = search(args.search, top_k=args.top_k, model_path=_DEFAULT_MODEL)

    if not results:
        _print("No results found.", style="yellow")
        return

    if _RICH:
        console.rule(f"[bold blue]Search: {args.search!r}[/bold blue]")
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("#", justify="right", style="dim")
        table.add_column("File", style="cyan")
        table.add_column("Score", justify="right")
        table.add_column("Snippet")
        for rank, r in enumerate(results, 1):
            table.add_row(str(rank), r["filename"], f"{r['score']:.4f}", r["snippet"])
        console.print(table)
    else:
        print(f"\nSearch: {args.search!r}")
        print("-" * 60)
        for rank, r in enumerate(results, 1):
            print(f"{rank}. {r['filename']}  (score: {r['score']:.4f})")
            print(f"   {r['snippet'][:200]}")
            print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Local AI Document Intelligence Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  uv run python main.py --input ./docs\n"
            "  uv run python main.py --search \"payments due in January\"\n"
            "  uv run python main.py --search \"Python developer\" --top-k 3\n"
        ),
    )
    parser.add_argument(
        "--input", metavar="PATH",
        help="Folder of PDF/TXT files. Runs full pipeline.",
    )
    parser.add_argument(
        "--search", metavar="QUERY",
        help="Semantic search query. Requires index built via --input first.",
    )
    parser.add_argument(
        "--top-k", metavar="N", type=int, default=5,
        help="Number of search results (default: 5).",
    )
    parser.add_argument(
        "--output", metavar="PATH", default="./output.json",
        help="Where to write output.json (default: ./output.json).",
    )
    parser.add_argument(
        "--rebuild-index", action="store_true",
        help="Force rebuild FAISS index even if one already exists.",
    )

    args = parser.parse_args()

    if args.input and args.search:
        parser.error("Use either --input or --search, not both.")
    if not args.input and not args.search:
        parser.print_help()
        sys.exit(0)

    if args.input:
        _run_pipeline(args)
    else:
        _run_search(args)


if __name__ == "__main__":
    main()

"""CLI for ingesting PDFs."""
from pathlib import Path
import sys
import logging
from .config import get_settings
from .ingest import ingest_pdf
def run_ingest_cli() -> None:
    """`uv run legatum-rag-ingest <file.pdf>`"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )
    get_settings().export_provider_env()
    args = sys.argv[1:]
    if not args:
        print("usage: legatum-rag-ingest <file.pdf>")
        raise SystemExit(2)
    pdf = Path(args[0])
    if not pdf.exists():
        print(f"file not found: {pdf}")
        raise SystemExit(1)
    res = ingest_pdf(pdf)
    print(f"ingested {pdf.name} → {res.doc_id} ({res.pages} pages)")

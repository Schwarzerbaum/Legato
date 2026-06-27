"""FastAPI application factory and console entrypoints."""
from __future__ import annotations
from fastapi import FastAPI
from . import __version__
from .config import get_settings
def create_app() -> FastAPI:
    settings = get_settings()
    settings.export_provider_env()
    app = FastAPI(title="LEGATUM RAG", version=__version__)
    return app
app = create_app()
@app.get("/health")
def health() -> dict:
    from .db import db_available
    return {
        "status": "ok",
        "service": "legatum-rag",
        "version": __version__,
        "db": db_available(),
    }
def run() -> None:
    """`uv run legatum-rag` → dev server with autoreload."""
    import uvicorn
    settings = get_settings()
    uvicorn.run(
        "legatum_rag.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
    )

"""
LEGATUM Backend — entry point
Run: uvicorn backend.main:app --reload --port 8000
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from legatum_intelligence.router import router as intelligence_router
from legatum_bank_engine.l6_knowledge_graph import seed_demo_graph

app = FastAPI(
    title="LEGATUM API",
    version="2.0.0",
    description="9-layer AI Philanthropic Banking — LBBW HackXplore 2026",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(intelligence_router, prefix="/api/v1/legatum")

@app.get("/health")
def health():
    return {"status": "ok", "version": "2.0.0"}

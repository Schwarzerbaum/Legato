#!/usr/bin/env python3
"""LEGATUM API server — port 9100.

Routes:
  /api/legatum       — construction AI (existing BlackSwanX modules)
  /api/user-engine   — L1 L4 L5 L7 L8 L9  (donor-facing layers)
  /api/bank-engine   — L2 L3 L6            (LBBW analyst layers)
"""
import sys
from pathlib import Path

# Make sure backend + engine packages are importable
ROOT = Path(__file__).parent
BACKEND = ROOT / "backend"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BACKEND))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from backend.api.legatum     import router as legatum_router
from backend.api.user_engine import router as user_engine_router
from backend.api.bank_engine import router as bank_engine_router

app = FastAPI(
    title="LEGATUM API",
    version="2.0.0",
    description="9-layer AI philanthropic banking — LBBW HackXplore 2026",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Construction AI (legacy)
app.include_router(legatum_router,      prefix="/api/legatum",      tags=["legatum-construction"])
# Philanthropic banking engines
app.include_router(user_engine_router,  prefix="/api/user-engine",  tags=["user-engine"])
app.include_router(bank_engine_router,  prefix="/api/bank-engine",  tags=["bank-engine"])

# Also serve extracted images
IMAGES_DIR = ROOT / "legatum" / "extracted_images"
IMAGES_DIR.mkdir(exist_ok=True)
app.mount("/extracted-images", StaticFiles(directory=str(IMAGES_DIR)), name="images")

@app.get("/health")
def health():
    return {"status": "ok", "server": "legatum-api"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("legatum_api:app", host="0.0.0.0", port=9100, reload=False)

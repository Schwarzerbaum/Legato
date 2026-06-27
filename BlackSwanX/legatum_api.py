#!/usr/bin/env python3
"""Minimal FastAPI server exposing only the legatum routes on port 9100."""
import sys
from pathlib import Path

# Make sure backend package is importable
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from backend.api.legatum import router as legatum_router

app = FastAPI(title="LEGATUM API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(legatum_router, prefix="/api/legatum", tags=["legatum"])

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

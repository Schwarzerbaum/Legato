"""BlackSwanX — FastAPI entry point."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.database.db import init_db
from backend.api.analysis import router as analysis_router
from backend.api.simulation import router as simulation_router
from backend.api.report import router as report_router
from backend.api.chat import router as chat_router
from backend.api.system import router as system_router
from backend.api.datev import router as datev_router
from backend.api.accounting import router as accounting_router
from backend.api.neural import router as neural_router
from backend.api.legatum import router as legatum_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="BlackSwanX",
    description="Local-first Social Intelligence Engine",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(system_router, prefix="/api/system", tags=["system"])
app.include_router(analysis_router, prefix="/api/analysis", tags=["analysis"])
app.include_router(simulation_router, prefix="/api/simulation", tags=["simulation"])
app.include_router(report_router, prefix="/api/report", tags=["report"])
app.include_router(chat_router, prefix="/api/chat", tags=["chat"])
app.include_router(datev_router, prefix="/api/datev", tags=["datev"])
app.include_router(accounting_router, prefix="/api/accounting", tags=["accounting"])
app.include_router(neural_router, prefix="/api/neural", tags=["neural"])
app.include_router(legatum_router, prefix="/api/legatum", tags=["legatum"])


@app.get("/")
async def root():
    return {"name": "BlackSwanX", "version": "0.1.0", "status": "running"}

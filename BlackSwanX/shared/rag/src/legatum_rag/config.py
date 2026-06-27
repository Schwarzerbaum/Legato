"""Runtime configuration.
Settings load from the process environment and an optional ``.env`` file
(see ``.env.example``). Field names map case-insensitively to env vars, so
``DATABASE_URL`` fills :attr:`Settings.database_url`, ``MODEL`` fills
:attr:`Settings.model`, and so on.
"""
from __future__ import annotations
import os
from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
# .../shared/rag/src/legatum_rag/config.py -> parents[2] == .../shared/rag
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )
    # --- LLM (orchestrator / harvest / synthesis; provider-prefixed, swappable) ---
    google_api_key: str = ""
    gemini_api_key: str = ""
    anthropic_api_key: str = ""
    claude_api_key: str = ""
    model: str = "anthropic:claude-haiku-4-5-20251001"
    # Point the LLM at a local OpenAI-compatible server (e.g. LM Studio) by
    # setting LLM_BASE_URL + using an `openai:<model>` MODEL. Empty → cloud.
    llm_base_url: str = ""
    llm_api_key: str = "lm-studio"
    # --- Multimodal retrieval (ColModernVBERT — MIT, ~250M, CPU/MPS) ---
    embed_model: str = "ModernVBERT/colmodernvbert"
    # auto → mps on Apple Silicon, else cuda, else cpu.
    embed_device: str = "auto"
    # --- OCR (DeepSeek-OCR-2 served locally via LM Studio, OpenAI-compatible) ---
    ocr_enabled: bool = True
    ocr_base_url: str = "http://localhost:1234/v1"
    ocr_model: str = "deepseek-ocr-2"
    ocr_api_key: str = "lm-studio"
    ocr_max_tokens: int = 4096
    ocr_frequency_penalty: float = 0.4
    # --- Postgres (property graph + multi-vector store via VectorChord) ---
    database_url: str = (
        "postgresql://legatum:legatum@127.0.0.1:5433/legatum_rag"
    )
    # --- Harvest (windowed entity/relation extraction) ---
    harvest_window: int = 3
    harvest_overlap: int = 1
    harvest_on_ingest: bool = True
    curate_on_harvest: bool = True
    # --- OKF wiki bundle + corpus/data dirs (in-tree by default) ---
    okf_dir: Path = _PROJECT_ROOT / "okf"
    data_dir: Path = _PROJECT_ROOT / "data"
    # --- saved workflow runs ---
    runs_dir: Path = _PROJECT_ROOT / "runs"
    # --- sandbox: real filesystem + shell, scoped to workspace_dir ---
    sandbox: bool = True
    workspace_dir: Path = _PROJECT_ROOT / "workspace"
    # --- workflow interpreter: per-eval wall-clock budget (seconds) ---
    interpreter_timeout: int = 600
    # --- server ---
    host: str = "127.0.0.1"
    port: int = 8000
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    @property
    def pages_dir(self) -> Path:
        """Where rendered PDF page images land."""
        return self.data_dir / "pages"
    @property
    def corpus_dir(self) -> Path:
        """Where uploaded source PDFs are stored."""
        return self.data_dir / "corpus"
    def export_provider_env(self) -> None:
        """Surface keys under the var names each provider SDK expects."""
        gemini = (
            self.google_api_key
            or self.gemini_api_key
            or os.environ.get("GEMINI_API_KEY", "")
        )
        if gemini:
            os.environ.setdefault("GOOGLE_API_KEY", gemini)
        anthropic = (
            self.anthropic_api_key
            or self.claude_api_key
            or os.environ.get("CLAUDE_API_KEY", "")
        )
        if anthropic:
            os.environ.setdefault("ANTHROPIC_API_KEY", anthropic)
@lru_cache
def get_settings() -> Settings:
    return Settings()

"""Postgres access — a thin psycopg helper plus schema initialization."""
from __future__ import annotations
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator
from .config import get_settings
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = _PROJECT_ROOT / "db" / "schema.sql"
def _require_psycopg():
    try:
        import psycopg  # noqa: PLC0415
    except ModuleNotFoundError as exc:  # pragma: no cover
        raise RuntimeError(
            "psycopg is not installed — run `uv add 'psycopg[binary]'`."
        ) from exc
    return psycopg
@contextmanager
def connect() -> Iterator[Any]:
    """Yield a psycopg connection to ``DATABASE_URL`` (autocommit off)."""
    psycopg = _require_psycopg()
    conn = psycopg.connect(get_settings().database_url)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
def db_available() -> bool:
    """True if we can open a connection right now (used for graceful degrade)."""
    try:
        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        return True
    except Exception:
        return False
def init_schema() -> str:
    """Apply ``db/schema.sql``. Returns a short status string."""
    sql = SCHEMA_PATH.read_text(encoding="utf-8")
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
    return f"applied schema from {SCHEMA_PATH}"
def run_initdb() -> None:
    """`uv run legatum-rag-initdb` — create extensions + tables."""
    print(init_schema())

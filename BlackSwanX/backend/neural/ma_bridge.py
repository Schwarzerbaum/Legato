"""M&A Pheromone Bridge — connects adversarial_pollination to the neural layer.

The adversarial_pollination module deposits three M&A-specific signal types
into ``ma_signals``:

    PREDATOR_SCENT  buyer risk (MAC triggers, indemnity leaks, …)
    PREY_SCENT      seller protection (caps, knowledge qualifiers, …)
    DISSONANCE      both swarms clashed — deal-break hot-zone

These are *not* in the neural ``PheromoneType`` enum because they originate
from a different semantic domain (M&A contract analysis vs. accounting).
However, they carry equivalent biological meaning and should appear on the
shared neural heatmap so that the accounting organism can sense M&A risk.

Mapping strategy
----------------
PREDATOR_SCENT  → DANGER_MARKER   (buyer risk = systemic danger)
PREY_SCENT      → OPPORTUNITY_BLOOM (seller protection = potential upside)
DISSONANCE      → ANOMALY_SCENT   (clash zones = the strongest anomaly signal)

Usage
-----
Call ``bridge_ma_signals(db)`` after each adversarial pollination run or from
the neural tick to pull recent M&A signals into the pheromone environment::

    from backend.neural.ma_bridge import bridge_ma_signals
    await bridge_ma_signals()
"""

from __future__ import annotations

import logging
import sqlite3
import time
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 1. The canonical mapping — exported so tests can verify it
# ---------------------------------------------------------------------------

from backend.neural.pheromones import PheromoneType

MA_TO_NEURAL_PHEROMONE: dict[str, PheromoneType] = {
    "PREDATOR_SCENT": PheromoneType.DANGER_MARKER,
    "PREY_SCENT":     PheromoneType.OPPORTUNITY_BLOOM,
    "DISSONANCE":     PheromoneType.ANOMALY_SCENT,
    # Also handle the generic signal types emitted by signal_pheromones.py
    "RISK_PULSE":     PheromoneType.DANGER_MARKER,
    "ANOMALY_SCENT":  PheromoneType.ANOMALY_SCENT,
    "CHAIN_TRIGGER":  PheromoneType.ASSET_TRAIL,
    "DRIFT_MARKER":   PheromoneType.STATE_RESIDUE,
    "ABSENCE_FLAG":   PheromoneType.URGENCY_ALARM,
    "OPPORTUNITY_BLOOM": PheromoneType.OPPORTUNITY_BLOOM,
    "AUDIT_BEACON":   PheromoneType.DANGER_MARKER,
}


# ---------------------------------------------------------------------------
# 2. Bridge function — pull fresh ma_signals into PheromoneEnvironment
# ---------------------------------------------------------------------------

def bridge_ma_signals(
    db_path: str = "",
    max_rows: int = 50,
    min_strength: float = 0.3,
) -> int:
    """Pull active M&A signals from ma_signals into the neural pheromone env.

    Uses synchronous SQLite (ma module uses sync SQLite, not async SQLAlchemy).
    Creates ``Pheromone`` objects and deposits them in the in-memory
    ``PheromoneEnvironment`` singleton.

    Parameters
    ----------
    db_path:
        Path to the SQLite database.  Defaults to the standard location
        ``backend/blackswanx.db`` derived from ``backend.config.settings``.
    max_rows:
        Maximum number of recent signals to bridge per call.
    min_strength:
        Only bridge signals whose strength >= this value (avoids noise).

    Returns
    -------
    int
        Number of pheromones deposited.
    """
    import asyncio
    import os

    if not db_path:
        from backend.config import settings
        # settings.database_url is "sqlite+aiosqlite:///…" — strip the prefix
        raw_url = settings.database_url
        db_path = raw_url.replace("sqlite+aiosqlite:///", "")
        if not os.path.isabs(db_path):
            db_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                db_path,
            )

    if not os.path.exists(db_path):
        logger.warning("bridge_ma_signals: database not found at %s", db_path)
        return 0

    from backend.neural.pheromones import (
        get_environment,
        create_pheromone,
        Pheromone,
    )

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    try:
        rows = conn.execute(
            """SELECT signal_type, source_entity, source_chunk_id, source_doc_id,
                      strength, payload, created_at
               FROM ma_signals
               WHERE is_active = 1 AND strength >= ?
               ORDER BY strength DESC, created_at DESC
               LIMIT ?""",
            (min_strength, max_rows),
        ).fetchall()
    except sqlite3.OperationalError as exc:
        logger.warning("bridge_ma_signals: ma_signals table not found: %s", exc)
        conn.close()
        return 0
    finally:
        conn.close()

    env = get_environment()
    deposited = 0

    for row in rows:
        ma_type = row["signal_type"]
        neural_type = MA_TO_NEURAL_PHEROMONE.get(ma_type)
        if neural_type is None:
            continue

        # Use doc_id:chunk_id as the position node
        position = f"ma_doc_{row['source_doc_id']}_chunk_{row['source_chunk_id']}"
        agent = f"ma_{ma_type.lower()}"

        pheromone = create_pheromone(
            ptype=neural_type,
            intensity=float(row["strength"]),
            position=position,
            source_agent=agent,
            payload={
                "ma_signal_type": ma_type,
                "source_entity": row["source_entity"],
                "doc_id": row["source_doc_id"],
                "chunk_id": row["source_chunk_id"],
            },
        )

        # Deposit synchronously using asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Inside an async context — schedule as task
                loop.create_task(env.deposit(pheromone))
            else:
                loop.run_until_complete(env.deposit(pheromone))
        except RuntimeError:
            # No running loop — create one
            asyncio.run(env.deposit(pheromone))

        deposited += 1

    if deposited:
        logger.info(
            "bridge_ma_signals: deposited %d M&A pheromones into neural env",
            deposited,
        )

    return deposited

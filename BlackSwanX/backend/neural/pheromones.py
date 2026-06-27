"""Stigmergic Living Ledger — Digital Pheromone System for BlackSwanX.

Agents deposit pheromones on financial entities (bookings, invoices, bank
transactions) as they process them.  When multiple agents independently
flag the same entity, intensities compound super-linearly — errors and
opportunities surface automatically on the dashboard heatmap.

Architecture
------------
In-memory buffer (`PheromoneEnvironment._deposits`) gives sub-ms query
times for real-time heatmap rendering.  Persistence to
`pheromone_deposits` via SQLAlchemy async keeps history across restarts.

Amplification Rules
-------------------
1. Same pheromone type + same target entity + *different* agent:
       combined = min(1.0, existing + new * 0.5)
2. Entity-level intensity sum with 3+ distinct agents:
       total *= 1.3  (super-linear swarm signal)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import PheromoneDeposit


# ---------------------------------------------------------------------------
# 1. Pheromone Types
# ---------------------------------------------------------------------------

class PheromoneType(str, Enum):
    """Scent vocabulary shared by all agents in the organism."""

    ASSET_TRAIL = "asset_trail"
    """Asset movement patterns — cash flow, transfers, account migrations."""

    ANOMALY_SCENT = "anomaly_scent"
    """Fraud / anomaly signals — Benford violations, duplicate amounts."""

    URGENCY_ALARM = "urgency_alarm"
    """Time-critical — tax deadlines, payment due dates, USt-VA filing."""

    OPPORTUNITY_BLOOM = "opportunity_bloom"
    """Tax savings, missed deductions, optimisation opportunities."""

    DANGER_MARKER = "danger_marker"
    """Risk signals — audit risk, compliance failure, GoBD violation."""

    STATE_RESIDUE = "state_residue"
    """System state changes — pipeline stage transitions, status flips."""

    REGULATORY_WIND = "regulatory_wind"
    """Legal / regulatory changes — BMF rulings, new UStG amendments."""

    LIQUIDITY_TRACE = "liquidity_trace"
    """Cash-flow path markers — liquidity corridors and bottlenecks."""


# ---------------------------------------------------------------------------
# 2. In-Memory Pheromone Representation
# ---------------------------------------------------------------------------

@dataclass
class Pheromone:
    """Single pheromone deposit living in the environment buffer."""

    type: PheromoneType
    intensity: float
    decay_rate: float
    position: str
    source_agent: str
    target_entity_type: Optional[str] = None
    target_entity_id: Optional[int] = None
    payload: Optional[dict] = None
    created_at: float = field(default_factory=time.time)

    # -- Derived properties -------------------------------------------------

    @property
    def current_intensity(self) -> float:
        """Apply exponential time-decay.  decay_rate is per-minute."""
        elapsed_minutes = (time.time() - self.created_at) / 60.0
        return self.intensity * (self.decay_rate ** elapsed_minutes)

    @property
    def is_expired(self) -> bool:
        """A pheromone is dead when its signal drops below 1 % of full."""
        return self.current_intensity < 0.01


# ---------------------------------------------------------------------------
# 3. Pheromone Environment  (singleton)
# ---------------------------------------------------------------------------

class PheromoneEnvironment:
    """Shared stigmergic environment — the colony's chemical workspace.

    All agents read from and write to the same ``PheromoneEnvironment``.
    The environment is the *only* coupling between agents; they never
    communicate directly.
    """

    def __init__(self) -> None:
        self._deposits: list[Pheromone] = []

    # -- Core operations ----------------------------------------------------

    async def deposit(
        self,
        pheromone: Pheromone,
        db: Optional[AsyncSession] = None,
    ) -> None:
        """Deposit a pheromone.  Amplifies if a compatible deposit exists.

        Amplification rule: if the *same* pheromone type targets the *same*
        entity but comes from a *different* agent, the existing deposit is
        boosted rather than duplicated::

            combined = min(1.0, existing.intensity + new.intensity * 0.5)
        """
        amplified = False
        if pheromone.target_entity_type and pheromone.target_entity_id is not None:
            for existing in self._deposits:
                if (
                    existing.type == pheromone.type
                    and existing.target_entity_type == pheromone.target_entity_type
                    and existing.target_entity_id == pheromone.target_entity_id
                    and existing.source_agent != pheromone.source_agent
                    and not existing.is_expired
                ):
                    existing.intensity = min(
                        1.0,
                        existing.intensity + pheromone.intensity * 0.5,
                    )
                    amplified = True
                    break

        if not amplified:
            self._deposits.append(pheromone)

        if db is not None:
            await self._persist_single(pheromone, db)

    # -- Query operations ---------------------------------------------------

    def sense(
        self,
        position: Optional[str] = None,
        pheromone_type: Optional[PheromoneType] = None,
        target_entity_type: Optional[str] = None,
        target_entity_id: Optional[int] = None,
    ) -> list[Pheromone]:
        """Return non-expired pheromones matching the given filters.

        Results are sorted by ``current_intensity`` descending so the
        strongest signal is always first.
        """
        results: list[Pheromone] = []
        for p in self._deposits:
            if p.is_expired:
                continue
            if position is not None and p.position != position:
                continue
            if pheromone_type is not None and p.type != pheromone_type:
                continue
            if target_entity_type is not None and p.target_entity_type != target_entity_type:
                continue
            if target_entity_id is not None and p.target_entity_id != target_entity_id:
                continue
            results.append(p)

        results.sort(key=lambda p: p.current_intensity, reverse=True)
        return results

    def get_entity_intensity(self, entity_type: str, entity_id: int) -> float:
        """Total pheromone intensity on a specific entity.

        Applies the **super-linear amplification** rule: when 3 or more
        distinct agents have deposited on the same entity the raw sum is
        multiplied by 1.3, making multi-agent consensus dramatically
        more visible on the heatmap.
        """
        agents: set[str] = set()
        total: float = 0.0

        for p in self._deposits:
            if (
                p.target_entity_type == entity_type
                and p.target_entity_id == entity_id
                and not p.is_expired
            ):
                total += p.current_intensity
                agents.add(p.source_agent)

        if len(agents) >= 3:
            total *= 1.3

        return total

    def evaporate(self) -> int:
        """Remove all expired pheromones from the in-memory buffer.

        Returns the number of evaporated deposits.
        """
        before = len(self._deposits)
        self._deposits = [p for p in self._deposits if not p.is_expired]
        return before - len(self._deposits)

    def get_strongest_trail(
        self,
        pheromone_type: PheromoneType,
    ) -> list[tuple[str, float]]:
        """Positions forming the strongest trail for *pheromone_type*.

        Returns ``[(position, intensity), ...]`` ordered by intensity
        descending.  Duplicate positions are collapsed to max intensity.
        """
        trail: dict[str, float] = {}
        for p in self._deposits:
            if p.type != pheromone_type or p.is_expired:
                continue
            ci = p.current_intensity
            if p.position not in trail or ci > trail[p.position]:
                trail[p.position] = ci

        return sorted(trail.items(), key=lambda t: t[1], reverse=True)

    # -- Heatmap outputs (dashboard-ready) ----------------------------------

    def get_heatmap(self) -> dict[str, dict[str, float]]:
        """Position-centric heatmap for the neural visualisation layer.

        Returns::

            {
                "position_node": {
                    "anomaly_scent": 0.87,
                    "urgency_alarm": 0.42,
                    ...
                },
                ...
            }
        """
        heatmap: dict[str, dict[str, float]] = {}
        for p in self._deposits:
            if p.is_expired:
                continue
            ci = p.current_intensity
            pos_map = heatmap.setdefault(p.position, {})
            type_key = p.type.value
            pos_map[type_key] = max(pos_map.get(type_key, 0.0), ci)
        return heatmap

    def get_entity_heatmap(self) -> dict[str, dict]:
        """Entity-centric heatmap — powers the *glowing bookings* UI.

        Returns::

            {
                "booking:42": {
                    "total_intensity": 1.74,
                    "types": {"anomaly_scent": 0.9, "danger_marker": 0.84},
                    "agent_count": 3
                },
                ...
            }
        """
        entities: dict[str, dict] = {}

        for p in self._deposits:
            if p.is_expired:
                continue
            if p.target_entity_type is None or p.target_entity_id is None:
                continue

            key = f"{p.target_entity_type}:{p.target_entity_id}"
            ci = p.current_intensity

            if key not in entities:
                entities[key] = {
                    "total_intensity": 0.0,
                    "types": {},
                    "agents": set(),
                }

            entry = entities[key]
            entry["total_intensity"] += ci
            type_key = p.type.value
            entry["types"][type_key] = max(
                entry["types"].get(type_key, 0.0), ci,
            )
            entry["agents"].add(p.source_agent)

        # Finalise: apply super-linear amplification and convert agent sets.
        result: dict[str, dict] = {}
        for key, entry in entities.items():
            agent_count = len(entry["agents"])
            total = entry["total_intensity"]
            if agent_count >= 3:
                total *= 1.3
            result[key] = {
                "total_intensity": total,
                "types": entry["types"],
                "agent_count": agent_count,
            }

        return result

    # -- Persistence --------------------------------------------------------

    async def persist(self, db: AsyncSession) -> None:
        """Bulk-insert all in-memory deposits into the database."""
        for p in self._deposits:
            await self._persist_single(p, db, flush=False)
        await db.flush()

    async def load(self, db: AsyncSession) -> None:
        """Load non-expired deposits from the database into memory."""
        now = datetime.now(timezone.utc)
        stmt = select(PheromoneDeposit).where(
            (PheromoneDeposit.expires_at.is_(None))
            | (PheromoneDeposit.expires_at > now)
        )
        result = await db.execute(stmt)
        rows = result.scalars().all()

        for row in rows:
            pheromone = Pheromone(
                type=PheromoneType(row.pheromone_type),
                intensity=row.intensity,
                decay_rate=row.decay_rate,
                position=row.position_node,
                source_agent=row.source_agent,
                target_entity_type=row.target_entity_type,
                target_entity_id=row.target_entity_id,
                payload=row.payload,
                created_at=row.created_at.timestamp() if row.created_at else time.time(),
            )
            if not pheromone.is_expired:
                self._deposits.append(pheromone)

    def clear(self) -> None:
        """Flush the in-memory buffer (does not touch the database)."""
        self._deposits.clear()

    # -- Internal helpers ---------------------------------------------------

    @staticmethod
    async def _persist_single(
        p: Pheromone,
        db: AsyncSession,
        flush: bool = True,
    ) -> None:
        """Write a single pheromone to the ``pheromone_deposits`` table."""
        created_dt = datetime.fromtimestamp(p.created_at, tz=timezone.utc).replace(tzinfo=None)

        # Estimate expiry: solve  intensity * decay_rate^t < 0.01
        # => t > log(0.01 / intensity) / log(decay_rate)
        if p.decay_rate < 1.0 and p.intensity > 0.0:
            import math
            minutes_to_expire = math.log(0.01 / p.intensity) / math.log(p.decay_rate)
            expires_dt = created_dt + timedelta(minutes=max(0.0, minutes_to_expire))
        else:
            expires_dt = None

        row = PheromoneDeposit(
            pheromone_type=p.type.value,
            intensity=p.intensity,
            decay_rate=p.decay_rate,
            position_node=p.position,
            target_entity_type=p.target_entity_type,
            target_entity_id=p.target_entity_id,
            payload=p.payload,
            source_agent=p.source_agent,
            created_at=created_dt,
            expires_at=expires_dt,
        )
        db.add(row)
        if flush:
            await db.flush()


# ---------------------------------------------------------------------------
# 4. Module-level Singleton
# ---------------------------------------------------------------------------

_env: PheromoneEnvironment | None = None


def get_environment() -> PheromoneEnvironment:
    """Get (or create) the global pheromone environment singleton."""
    global _env
    if _env is None:
        _env = PheromoneEnvironment()
    return _env


# ---------------------------------------------------------------------------
# 5. Helper / Convenience Functions
# ---------------------------------------------------------------------------

def create_pheromone(
    ptype: PheromoneType,
    intensity: float,
    position: str,
    source_agent: str,
    target_entity_type: Optional[str] = None,
    target_entity_id: Optional[int] = None,
    payload: Optional[dict] = None,
    decay_rate: float = 0.95,
) -> Pheromone:
    """Factory for creating a ``Pheromone`` with validated intensity."""
    return Pheromone(
        type=ptype,
        intensity=max(0.0, min(1.0, intensity)),
        decay_rate=decay_rate,
        position=position,
        source_agent=source_agent,
        target_entity_type=target_entity_type,
        target_entity_id=target_entity_id,
        payload=payload,
    )


async def deposit_on_entity(
    db: AsyncSession,
    ptype: PheromoneType,
    intensity: float,
    source_agent: str,
    entity_type: str,
    entity_id: int,
    payload: Optional[dict] = None,
) -> None:
    """One-liner: create a pheromone, deposit it, and persist to DB.

    Usage::

        await deposit_on_entity(
            db,
            PheromoneType.ANOMALY_SCENT,
            intensity=0.85,
            source_agent="benford_agent",
            entity_type="booking",
            entity_id=42,
            payload={"rule": "first_digit", "deviation": 0.23},
        )
    """
    env = get_environment()
    pheromone = create_pheromone(
        ptype=ptype,
        intensity=intensity,
        position=f"{entity_type}:{entity_id}",
        source_agent=source_agent,
        target_entity_type=entity_type,
        target_entity_id=entity_id,
        payload=payload,
    )
    await env.deposit(pheromone, db=db)

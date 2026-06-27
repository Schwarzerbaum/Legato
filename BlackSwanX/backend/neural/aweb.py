"""AWEB -- Adaptive Web Vascular Data Routing System.

The organism's circulatory system.  Data is oxygen.  Agents are cells.
AWEB ensures every cell gets fed by routing data through healthy "veins"
and auto-rerouting when veins fail.

Architecture:
    Vein                In-memory representation of a data pathway
    AWEB                Singleton vascular network -- register, route, heal
    VeinStatus          healthy | degraded | blocked
    SourceType          bank_api | crawler | file_import | ollama | elster

Routing algorithm:
    1. Caller requests a vein by ID via ``aweb.route(vein_id)``
    2. If healthy  -> return immediately
    3. If degraded -> return with a warning (still functional)
    4. If blocked  -> walk the fallback chain (max depth from config)
    5. If chain exhausted -> return None (caller must handle)

Persistence:
    All veins are kept in memory for sub-ms routing latency and
    flushed to the ``aweb_veins`` SQLite table via ``persist()``.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.database.models import AWEBVein

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class VeinStatus(str, Enum):
    """Health state of a data vein."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    BLOCKED = "blocked"


class SourceType(str, Enum):
    """Category of data source behind a vein."""

    BANK_API = "bank_api"
    CRAWLER = "crawler"
    FILE_IMPORT = "file_import"
    OLLAMA = "ollama"
    ELSTER = "elster"


# ---------------------------------------------------------------------------
# Vein dataclass
# ---------------------------------------------------------------------------

@dataclass
class Vein:
    """In-memory representation of a single data pathway.

    Tracks health via an exponential moving average of latency and a
    monotonic failure counter that drives automatic status transitions.
    """

    vein_id: str
    source_type: SourceType
    endpoint_url: str = ""
    status: VeinStatus = VeinStatus.HEALTHY
    last_heartbeat: float = field(default_factory=time.time)
    avg_latency_ms: float = 0.0
    failure_count: int = 0
    fallback_vein_id: str | None = None

    # -- queries -------------------------------------------------------------

    def is_available(self) -> bool:
        """Return ``True`` if the vein is not blocked."""
        return self.status != VeinStatus.BLOCKED

    # -- mutation ------------------------------------------------------------

    def record_success(self, latency_ms: float) -> None:
        """Record a successful operation with observed *latency_ms*.

        Latency is smoothed via EMA (alpha=0.2).  If the vein was degraded
        it is promoted back to healthy and the failure counter is reset.
        """
        self.avg_latency_ms = self.avg_latency_ms * 0.8 + latency_ms * 0.2
        self.last_heartbeat = time.time()
        if self.status == VeinStatus.DEGRADED:
            self.failure_count = 0
            self.status = VeinStatus.HEALTHY
            logger.info("vein %s recovered -> HEALTHY", self.vein_id)

    def record_failure(self) -> None:
        """Record a failed operation.

        Automatically transitions:
            * 3+ failures  -> DEGRADED
            * 10+ failures -> BLOCKED
        Thresholds are read from ``settings`` so they stay in sync with
        the config file.
        """
        self.failure_count += 1
        if self.failure_count >= settings.aweb_block_after_failures:
            if self.status != VeinStatus.BLOCKED:
                self.status = VeinStatus.BLOCKED
                logger.warning(
                    "vein %s BLOCKED after %d failures",
                    self.vein_id,
                    self.failure_count,
                )
        elif self.failure_count >= settings.aweb_degrade_after_failures:
            if self.status != VeinStatus.DEGRADED:
                self.status = VeinStatus.DEGRADED
                logger.warning(
                    "vein %s DEGRADED after %d failures",
                    self.vein_id,
                    self.failure_count,
                )

    def reset(self) -> None:
        """Reset the vein to a pristine healthy state."""
        self.status = VeinStatus.HEALTHY
        self.failure_count = 0
        self.avg_latency_ms = 0.0
        self.last_heartbeat = time.time()


# ---------------------------------------------------------------------------
# AWEB -- the vascular system (singleton)
# ---------------------------------------------------------------------------

class AWEB:
    """Adaptive Web vascular network.

    Maintains the full set of registered veins in memory and provides
    routing, fallback resolution, heartbeat management, and persistence.
    """

    def __init__(self) -> None:
        self.veins: dict[str, Vein] = {}
        self._fallback_cache: dict[str, list[str]] = {}

    # -- registration --------------------------------------------------------

    def register_vein(self, vein: Vein) -> None:
        """Add *vein* to the network and rebuild the fallback cache."""
        self.veins[vein.vein_id] = vein
        self._rebuild_fallback_cache()

    def set_fallback(self, vein_id: str, fallback_id: str) -> None:
        """Assign *fallback_id* as the fallback for *vein_id*."""
        if vein_id not in self.veins:
            raise KeyError(f"Unknown vein: {vein_id}")
        if fallback_id not in self.veins:
            raise KeyError(f"Unknown fallback vein: {fallback_id}")
        self.veins[vein_id].fallback_vein_id = fallback_id
        self._rebuild_fallback_cache()

    # -- routing -------------------------------------------------------------

    async def route(self, vein_id: str) -> Vein | None:
        """Route to the best available vein starting from *vein_id*.

        Returns the vein itself if healthy or degraded (with a warning).
        If blocked, walks the precomputed fallback chain up to
        ``settings.aweb_max_fallback_depth`` hops.  Returns ``None`` when
        no usable vein can be found.
        """
        vein = self.veins.get(vein_id)
        if vein is None:
            logger.error("route() called for unknown vein: %s", vein_id)
            return None

        if vein.status == VeinStatus.HEALTHY:
            return vein

        if vein.status == VeinStatus.DEGRADED:
            logger.warning(
                "routing through DEGRADED vein %s (failures=%d, latency=%.1fms)",
                vein.vein_id,
                vein.failure_count,
                vein.avg_latency_ms,
            )
            return vein

        # BLOCKED -- walk the fallback chain
        chain = self._fallback_cache.get(vein_id, [])
        for fallback_id in chain:
            fallback = self.veins.get(fallback_id)
            if fallback is None:
                continue
            if fallback.status != VeinStatus.BLOCKED:
                logger.info(
                    "vein %s blocked -> rerouted to %s",
                    vein_id,
                    fallback.vein_id,
                )
                return fallback

        logger.error(
            "vein %s blocked and no fallback available (chain=%s)",
            vein_id,
            chain,
        )
        return None

    async def execute_with_routing(
        self,
        vein_id: str,
        operation: Callable[..., Coroutine[Any, Any, Any]],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Execute *operation* through the best available vein.

        1. Route to the best vein.
        2. Execute the operation.
        3. On success -- record latency.
        4. On failure -- record failure, try one fallback, retry once.
        5. Raise if all attempts are exhausted.
        """
        vein = await self.route(vein_id)
        if vein is None:
            raise RuntimeError(
                f"No available vein for {vein_id} -- all fallbacks exhausted"
            )

        # First attempt
        start = time.time()
        try:
            result = await operation(*args, **kwargs)
            latency_ms = (time.time() - start) * 1000
            vein.record_success(latency_ms)
            return result
        except Exception as exc:
            vein.record_failure()
            logger.warning(
                "operation failed on vein %s: %s -- attempting fallback",
                vein.vein_id,
                exc,
            )

        # Fallback retry (one hop)
        fallback_vein = await self._next_fallback(vein)
        if fallback_vein is None:
            raise RuntimeError(
                f"Operation failed on {vein.vein_id} and no fallback available"
            )

        start = time.time()
        try:
            result = await operation(*args, **kwargs)
            latency_ms = (time.time() - start) * 1000
            fallback_vein.record_success(latency_ms)
            return result
        except Exception as exc:
            fallback_vein.record_failure()
            raise RuntimeError(
                f"Operation failed on fallback {fallback_vein.vein_id}: {exc}"
            ) from exc

    # -- fallback helpers ----------------------------------------------------

    def get_fallback_chain(self, vein_id: str) -> list[str]:
        """Return the full fallback chain for *vein_id*."""
        return list(self._fallback_cache.get(vein_id, []))

    def _rebuild_fallback_cache(self) -> None:
        """Precompute fallback chains for every vein (max depth from config)."""
        self._fallback_cache.clear()
        max_depth = settings.aweb_max_fallback_depth
        for vid in self.veins:
            chain: list[str] = []
            current = self.veins[vid]
            seen: set[str] = {vid}
            for _ in range(max_depth):
                fb = current.fallback_vein_id
                if fb is None or fb in seen or fb not in self.veins:
                    break
                chain.append(fb)
                seen.add(fb)
                current = self.veins[fb]
            if chain:
                self._fallback_cache[vid] = chain

    async def _next_fallback(self, vein: Vein) -> Vein | None:
        """Return the first non-blocked fallback for *vein*, or ``None``."""
        chain = self._fallback_cache.get(vein.vein_id, [])
        for fb_id in chain:
            fb = self.veins.get(fb_id)
            if fb is not None and fb.status != VeinStatus.BLOCKED:
                return fb
        return None

    # -- heartbeat -----------------------------------------------------------

    async def heartbeat(
        self,
        vein_id: str,
        check_fn: Callable[..., Coroutine[Any, Any, Any]] | None = None,
    ) -> None:
        """Run a health check on a single vein.

        If *check_fn* is provided it is awaited and the result is recorded
        as success/failure.  Otherwise the heartbeat timestamp is simply
        refreshed.
        """
        vein = self.veins.get(vein_id)
        if vein is None:
            logger.warning("heartbeat for unknown vein: %s", vein_id)
            return

        if check_fn is None:
            vein.last_heartbeat = time.time()
            return

        start = time.time()
        try:
            await check_fn()
            latency_ms = (time.time() - start) * 1000
            vein.record_success(latency_ms)
        except Exception as exc:
            vein.record_failure()
            logger.warning("heartbeat failed for %s: %s", vein_id, exc)

    async def heartbeat_all(self) -> None:
        """Run a heartbeat on every registered vein (timestamp only).

        For veins that have not reported a heartbeat in longer than
        ``settings.aweb_heartbeat_interval`` seconds the failure counter
        is incremented which may trigger degradation or blocking.
        """
        now = time.time()
        threshold = settings.aweb_heartbeat_interval
        for vein in self.veins.values():
            age = now - vein.last_heartbeat
            if age > threshold * 3:
                vein.record_failure()
                logger.warning(
                    "vein %s missed heartbeat (%.0fs old)", vein.vein_id, age
                )
            else:
                vein.last_heartbeat = now

    # -- reporting -----------------------------------------------------------

    def get_health_report(self) -> dict[str, Any]:
        """Return a full health snapshot of the vascular system."""
        healthy_count = 0
        degraded: list[dict[str, Any]] = []
        blocked: list[dict[str, Any]] = []
        by_type: dict[str, dict[str, int]] = {}

        for vein in self.veins.values():
            # Per-type counts
            st = vein.source_type.value
            if st not in by_type:
                by_type[st] = {"healthy": 0, "degraded": 0, "blocked": 0}

            if vein.status == VeinStatus.HEALTHY:
                healthy_count += 1
                by_type[st]["healthy"] += 1
            elif vein.status == VeinStatus.DEGRADED:
                degraded.append({
                    "vein_id": vein.vein_id,
                    "failure_count": vein.failure_count,
                    "avg_latency_ms": round(vein.avg_latency_ms, 2),
                })
                by_type[st]["degraded"] += 1
            elif vein.status == VeinStatus.BLOCKED:
                blocked.append({
                    "vein_id": vein.vein_id,
                    "failure_count": vein.failure_count,
                    "fallback": vein.fallback_vein_id,
                })
                by_type[st]["blocked"] += 1

        return {
            "total_veins": len(self.veins),
            "healthy": healthy_count,
            "degraded": degraded,
            "blocked": blocked,
            "by_type": by_type,
        }

    # -- persistence ---------------------------------------------------------

    async def persist(self, db: AsyncSession) -> None:
        """Upsert all in-memory veins to the ``aweb_veins`` table."""
        for vein in self.veins.values():
            result = await db.execute(
                select(AWEBVein).where(AWEBVein.vein_id == vein.vein_id)
            )
            row = result.scalar_one_or_none()
            if row is None:
                row = AWEBVein(vein_id=vein.vein_id)
                db.add(row)
            row.source_type = vein.source_type.value
            row.endpoint_url = vein.endpoint_url
            row.status = vein.status.value
            row.last_heartbeat = _epoch_to_datetime(vein.last_heartbeat)
            row.avg_latency_ms = vein.avg_latency_ms
            row.failure_count = vein.failure_count
            row.fallback_vein_id = vein.fallback_vein_id
        await db.commit()

    async def load(self, db: AsyncSession) -> None:
        """Load veins from the database into memory, replacing current state."""
        result = await db.execute(select(AWEBVein))
        rows = result.scalars().all()
        self.veins.clear()
        for row in rows:
            vein = Vein(
                vein_id=row.vein_id,
                source_type=SourceType(row.source_type),
                endpoint_url=row.endpoint_url or "",
                status=VeinStatus(row.status),
                last_heartbeat=(
                    row.last_heartbeat.timestamp()
                    if row.last_heartbeat
                    else time.time()
                ),
                avg_latency_ms=row.avg_latency_ms or 0.0,
                failure_count=row.failure_count or 0,
                fallback_vein_id=row.fallback_vein_id,
            )
            self.veins[vein.vein_id] = vein
        self._rebuild_fallback_cache()
        logger.info("AWEB loaded %d veins from database", len(self.veins))

    def clear(self) -> None:
        """Reset the vascular system -- remove all veins."""
        self.veins.clear()
        self._fallback_cache.clear()


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_aweb: AWEB | None = None


def get_aweb() -> AWEB:
    """Return the global AWEB singleton, creating it on first access."""
    global _aweb
    if _aweb is None:
        _aweb = AWEB()
    return _aweb


# ---------------------------------------------------------------------------
# Default veins
# ---------------------------------------------------------------------------

def create_default_veins() -> list[Vein]:
    """Pre-register the standard BlackSwanX data veins.

    Returns a list of ``Vein`` instances with sensible defaults for the
    organism's expected data sources.  Fallback relationships:

        crawler_twitter     -> crawler_duckduckgo
        ollama_assassin     -> ollama_swarm
        file_import_bank_csv -> file_import_datev
    """
    ollama_url = settings.ollama_base_url

    veins = [
        # Crawlers
        Vein(vein_id="crawler_duckduckgo", source_type=SourceType.CRAWLER),
        Vein(vein_id="crawler_reddit", source_type=SourceType.CRAWLER),
        Vein(vein_id="crawler_hackernews", source_type=SourceType.CRAWLER),
        Vein(vein_id="crawler_youtube", source_type=SourceType.CRAWLER),
        Vein(vein_id="crawler_twitter", source_type=SourceType.CRAWLER),
        Vein(vein_id="crawler_bmf", source_type=SourceType.CRAWLER),
        # Ollama agents
        Vein(
            vein_id="ollama_swarm",
            source_type=SourceType.OLLAMA,
            endpoint_url=ollama_url,
        ),
        Vein(
            vein_id="ollama_assassin",
            source_type=SourceType.OLLAMA,
            endpoint_url=ollama_url,
        ),
        Vein(
            vein_id="ollama_nexus",
            source_type=SourceType.OLLAMA,
            endpoint_url=ollama_url,
        ),
        # File imports
        Vein(vein_id="file_import_datev", source_type=SourceType.FILE_IMPORT),
        Vein(vein_id="file_import_bank_csv", source_type=SourceType.FILE_IMPORT),
    ]

    # Set fallback relationships
    vein_map = {v.vein_id: v for v in veins}
    vein_map["crawler_twitter"].fallback_vein_id = "crawler_duckduckgo"
    vein_map["ollama_assassin"].fallback_vein_id = "ollama_swarm"
    vein_map["file_import_bank_csv"].fallback_vein_id = "file_import_datev"

    return veins


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------

async def initialize_aweb(db: AsyncSession | None = None) -> AWEB:
    """Create and populate the AWEB singleton with default veins.

    If a *db* session is provided the veins are also persisted to the
    ``aweb_veins`` table.
    """
    aweb = get_aweb()

    for vein in create_default_veins():
        aweb.register_vein(vein)

    logger.info(
        "AWEB initialized with %d veins (%d fallback chains)",
        len(aweb.veins),
        len(aweb._fallback_cache),
    )

    if db is not None:
        await aweb.persist(db)
        logger.info("AWEB veins persisted to database")

    return aweb


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _epoch_to_datetime(epoch: float) -> "datetime":
    """Convert a ``time.time()`` epoch float to a ``datetime`` for SQLAlchemy."""
    from datetime import datetime, timezone

    return datetime.fromtimestamp(epoch, tz=timezone.utc).replace(tzinfo=None)

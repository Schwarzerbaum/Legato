"""Neural Integration Layer -- Where Stigmergy Meets Saltatory Conduction.

This is the convergence point of BlackSwanX's bio-inspired communication
systems.  Three subsystems fuse into a single organism here:

    Pheromones (stigmergy)   -- indirect agent-to-agent communication
    Conduction (neural)      -- priority-routed signal transmission
    AWEB (vascular)          -- data-pathway health and routing

Other modules interact with a single entry point::

    bus = get_event_bus()
    await bus.emit("fraud_alert", {"booking_id": 42, "score": 0.9}, "CRITICAL")

The bus transparently:
    1. Deposits the right pheromone on the target entity
    2. Creates and transmits a NeuralSignal through myelinated pathways
    3. Checks apoptosis thresholds when needed
    4. Updates AWEB health metrics

Also houses the **Apoptosis Kill Switch** -- the organism's immune system.
When agent consensus drops below the configured threshold for an entity
type, the branch is terminated (killed) to prevent incorrect data from
propagating through the financial pipeline.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.database.models import ApoptosisLog
from backend.neural.aweb import AWEB, get_aweb, initialize_aweb
from backend.neural.conduction import (
    NeuralNetwork,
    NeuralSignal,
    NodeOfRanvier,
    SignalPriority,
    TransmitResult,
    create_default_financial_network,
    create_signal,
    get_network,
)
from backend.neural.pheromones import (
    Pheromone,
    PheromoneEnvironment,
    PheromoneType,
    create_pheromone,
    deposit_on_entity,
    get_environment,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1. Pheromone <-> Signal Conversion Mappings
# ---------------------------------------------------------------------------

PHEROMONE_TO_PRIORITY: dict[PheromoneType, SignalPriority] = {
    PheromoneType.URGENCY_ALARM: SignalPriority.CRITICAL,
    PheromoneType.DANGER_MARKER: SignalPriority.CRITICAL,
    PheromoneType.ANOMALY_SCENT: SignalPriority.HIGH,
    PheromoneType.OPPORTUNITY_BLOOM: SignalPriority.HIGH,
    PheromoneType.ASSET_TRAIL: SignalPriority.NORMAL,
    PheromoneType.LIQUIDITY_TRACE: SignalPriority.NORMAL,
    PheromoneType.STATE_RESIDUE: SignalPriority.LOW,
    PheromoneType.REGULATORY_WIND: SignalPriority.LOW,
}

PRIORITY_TO_PHEROMONE: dict[SignalPriority, PheromoneType] = {
    SignalPriority.CRITICAL: PheromoneType.DANGER_MARKER,
    SignalPriority.HIGH: PheromoneType.ANOMALY_SCENT,
    SignalPriority.NORMAL: PheromoneType.ASSET_TRAIL,
    SignalPriority.LOW: PheromoneType.STATE_RESIDUE,
}

EVENT_TO_PHEROMONE: dict[str, PheromoneType] = {
    "fraud_alert": PheromoneType.ANOMALY_SCENT,
    "anomaly_detected": PheromoneType.ANOMALY_SCENT,
    "tax_deadline": PheromoneType.URGENCY_ALARM,
    "payment_due": PheromoneType.URGENCY_ALARM,
    "deduction_found": PheromoneType.OPPORTUNITY_BLOOM,
    "optimization_available": PheromoneType.OPPORTUNITY_BLOOM,
    "audit_risk": PheromoneType.DANGER_MARKER,
    "compliance_failure": PheromoneType.DANGER_MARKER,
    "cashflow_alert": PheromoneType.LIQUIDITY_TRACE,
    "transfer_detected": PheromoneType.ASSET_TRAIL,
    "regulation_change": PheromoneType.REGULATORY_WIND,
    "pipeline_stage": PheromoneType.STATE_RESIDUE,
}


# ---------------------------------------------------------------------------
# 2. Pheromone-to-Signal Conversion
# ---------------------------------------------------------------------------

async def pheromone_to_signal(pheromone: Pheromone) -> NeuralSignal | None:
    """Convert a strong pheromone into a NeuralSignal for transmission.

    Only pheromones with ``current_intensity > 0.6`` are worth transmitting --
    weak scents are noise, strong scents carry actionable information.

    The pheromone type is mapped to a signal priority via
    ``PHEROMONE_TO_PRIORITY``, and the pheromone's payload is carried
    forward as the signal's data cargo.

    Returns ``None`` if the pheromone is too weak to warrant a signal.
    """
    if pheromone.current_intensity <= 0.6:
        return None

    priority = PHEROMONE_TO_PRIORITY.get(pheromone.type, SignalPriority.NORMAL)

    return create_signal(
        signal_type=f"pheromone_{pheromone.type.value}",
        priority=priority,
        payload=pheromone.payload or {},
        intensity=pheromone.current_intensity,
        source_node=pheromone.source_agent,
    )


# ---------------------------------------------------------------------------
# 3. Signal-to-Pheromone Feedback Loop
# ---------------------------------------------------------------------------

async def signal_to_pheromone(
    signal: NeuralSignal,
    node_id: str,
) -> Pheromone:
    """Deposit a feedback pheromone when a Node of Ranvier amplifies a signal.

    This creates the convergence loop: neural signals leave chemical traces
    that future agents can sense.  The deposit intensity is half the signal
    strength -- amplification echoes, but does not dominate.

    The signal's priority is reverse-mapped to a pheromone type via
    ``PRIORITY_TO_PHEROMONE``.
    """
    pheromone_type = PRIORITY_TO_PHEROMONE.get(
        signal.priority, PheromoneType.STATE_RESIDUE
    )

    return create_pheromone(
        ptype=pheromone_type,
        intensity=signal.intensity * 0.5,
        position=node_id,
        source_agent=f"neural_{signal.source_node}",
        payload=signal.payload,
        decay_rate=settings.pheromone_default_decay_rate,
    )


# ---------------------------------------------------------------------------
# 4. Auto-Myelination from Pheromone Trails
# ---------------------------------------------------------------------------

async def auto_myelinate_from_trails(
    env: PheromoneEnvironment,
    network: NeuralNetwork,
) -> int:
    """Scan pheromone trails and strengthen neural pathways they overlap.

    This is the CONVERGENCE mechanism: popular pheromone trails (positions
    visited frequently by many agents) map onto neural pathways.  When a
    trail consistently connects two nodes that share a pathway, the
    pathway's myelination score increases -- making future transmissions
    on that route use saltatory (fast) conduction.

    Returns the number of pathways that received a myelination boost.
    """
    myelinated_count = 0

    for (from_node, to_node), pathway in network.pathways.items():
        if pathway.is_myelinated:
            continue

        # Check pheromone intensity at both endpoints of the pathway
        deposits_from = env.sense(position=from_node)
        deposits_to = env.sense(position=to_node)

        if not deposits_from or not deposits_to:
            continue

        # Strong trail = both endpoints have high-intensity pheromones
        max_from = max(p.current_intensity for p in deposits_from)
        max_to = max(p.current_intensity for p in deposits_to)

        if max_from >= 0.5 and max_to >= 0.5:
            await network.myelinate_pathway(
                from_node,
                to_node,
                increment=settings.myelination_score_increment,
            )
            myelinated_count += 1
            logger.debug(
                "Trail-based myelination: %s -> %s (from=%.2f, to=%.2f)",
                from_node,
                to_node,
                max_from,
                max_to,
            )

    return myelinated_count


# ---------------------------------------------------------------------------
# 5. Apoptosis Result
# ---------------------------------------------------------------------------

@dataclass
class ApoptosisResult:
    """Outcome of an apoptosis (immune system kill switch) check.

    Attributes:
        killed:          True if the entity branch was terminated.
        entity_type:     Type of entity checked (ust_va, report, etc.).
        entity_id:       Database ID of the entity.
        consensus_score: Fraction of agents that agreed on the conclusion.
        threshold:       Minimum consensus required for survival.
        reason:          Human-readable explanation of the outcome.
    """

    killed: bool
    entity_type: str
    entity_id: int
    consensus_score: float
    threshold: float
    reason: str


# ---------------------------------------------------------------------------
# 6. Apoptosis Kill Switch
# ---------------------------------------------------------------------------

# Lookup table for entity-type-specific thresholds
_APOPTOSIS_THRESHOLDS: dict[str, str] = {
    "ust_va": "apoptosis_threshold_ust_va",
    "report": "apoptosis_threshold_report",
    "booking_batch": "apoptosis_threshold_categorization",
    "categorization": "apoptosis_threshold_categorization",
}


def _get_apoptosis_threshold(entity_type: str) -> float:
    """Resolve the apoptosis threshold for a given entity type from config."""
    attr_name = _APOPTOSIS_THRESHOLDS.get(entity_type)
    if attr_name is not None:
        return getattr(settings, attr_name)
    # Default to the categorization threshold for unknown entity types
    return settings.apoptosis_threshold_categorization


async def check_apoptosis(
    db: AsyncSession,
    entity_type: str,
    entity_id: int,
    agent_results: list[dict],
    threshold: float | None = None,
) -> ApoptosisResult:
    """The Immune System Kill Switch.

    Counts how many agents agree on the core conclusion for an entity,
    then decides whether the branch lives or dies.

    Each dict in *agent_results* must contain a ``"conclusion"`` key.
    Consensus is calculated as::

        agreements = count of most-common conclusion
        consensus  = agreements / total_agents

    If ``consensus < threshold``, the branch is KILLED:
        1. An ``ApoptosisLog`` row is persisted to the database.
        2. A ``DANGER_MARKER`` pheromone is deposited at maximum intensity.
        3. A CRITICAL neural signal is emitted through the network.

    Parameters
    ----------
    db : AsyncSession
        Active database session for logging and pheromone persistence.
    entity_type : str
        Entity category (ust_va, report, booking_batch, categorization).
    entity_id : int
        Database primary key of the entity under review.
    agent_results : list[dict]
        Each entry must have at least ``{"conclusion": ..., "agent_id": ...}``.
    threshold : float, optional
        Override the config-based threshold.  Defaults to the value
        looked up from ``settings`` based on *entity_type*.

    Returns
    -------
    ApoptosisResult
        Always returned -- check ``.killed`` to determine the outcome.
    """
    if threshold is None:
        threshold = _get_apoptosis_threshold(entity_type)

    total_agents = len(agent_results)
    if total_agents == 0:
        return ApoptosisResult(
            killed=True,
            entity_type=entity_type,
            entity_id=entity_id,
            consensus_score=0.0,
            threshold=threshold,
            reason="No agents provided results -- cannot validate",
        )

    # Count conclusions to find the majority
    conclusion_counts: dict[str, int] = {}
    for result in agent_results:
        conclusion = str(result.get("conclusion", ""))
        conclusion_counts[conclusion] = conclusion_counts.get(conclusion, 0) + 1

    max_agreements = max(conclusion_counts.values())
    consensus_score = max_agreements / total_agents

    if consensus_score >= threshold:
        return ApoptosisResult(
            killed=False,
            entity_type=entity_type,
            entity_id=entity_id,
            consensus_score=consensus_score,
            threshold=threshold,
            reason=(
                f"Consensus {consensus_score:.3f} meets threshold "
                f"{threshold:.3f} -- branch survives"
            ),
        )

    # --- KILL THE BRANCH ---
    reason = (
        f"Consensus {consensus_score:.3f} below threshold {threshold:.3f} "
        f"({max_agreements}/{total_agents} agents agree) -- branch terminated"
    )
    logger.warning(
        "APOPTOSIS triggered for %s:%d -- %s",
        entity_type,
        entity_id,
        reason,
    )

    # 1. Log to database
    agent_ids = [r.get("agent_id", "unknown") for r in agent_results]
    log_entry = ApoptosisLog(
        entity_type=entity_type,
        entity_id=entity_id,
        trigger_reason=reason,
        consensus_score=consensus_score,
        threshold_required=threshold,
        agents_involved=agent_ids,
    )
    db.add(log_entry)
    await db.flush()

    # 2. Deposit DANGER_MARKER pheromone at maximum intensity
    await deposit_on_entity(
        db=db,
        ptype=PheromoneType.DANGER_MARKER,
        intensity=1.0,
        source_agent="apoptosis_system",
        entity_type=entity_type,
        entity_id=entity_id,
        payload={
            "apoptosis": True,
            "consensus": consensus_score,
            "threshold": threshold,
            "reason": reason,
        },
    )

    # 3. Emit CRITICAL signal through neural network
    network = get_network()
    apoptosis_signal = create_signal(
        signal_type="apoptosis_trigger",
        priority=SignalPriority.CRITICAL,
        payload={
            "apoptosis": True,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "consensus": consensus_score,
            "threshold": threshold,
        },
        intensity=1.0,
        source_node="nexus_orchestrator",
    )
    await network.transmit(apoptosis_signal, db=db)

    return ApoptosisResult(
        killed=True,
        entity_type=entity_type,
        entity_id=entity_id,
        consensus_score=consensus_score,
        threshold=threshold,
        reason=reason,
    )


# ---------------------------------------------------------------------------
# 7. NeuralEventBus -- Unified Organism Communication Interface
# ---------------------------------------------------------------------------

class NeuralEventBus:
    """Unified interface for the organism's communication.

    Other modules interact with the entire neural-stigmergic system
    through a single call::

        bus = get_event_bus()
        await bus.emit("fraud_alert", {"booking_id": 42, "score": 0.9}, "CRITICAL")

    The bus handles:
        1. Depositing the appropriate pheromone type
        2. Creating and transmitting the neural signal
        3. Checking for apoptosis if needed
        4. Updating AWEB health metrics
    """

    def __init__(
        self,
        env: PheromoneEnvironment,
        network: NeuralNetwork,
        aweb: AWEB,
    ) -> None:
        self.env = env
        self.network = network
        self.aweb = aweb
        self._emit_count: int = 0

    async def emit(
        self,
        event_type: str,
        payload: dict,
        priority: str = "NORMAL",
        source_node: str = "system",
        target_entity_type: str | None = None,
        target_entity_id: int | None = None,
        db: AsyncSession | None = None,
    ) -> TransmitResult:
        """Emit an event through the organism's combined communication systems.

        Steps executed in order:
            1. Resolve pheromone type from *event_type*.
            2. Deposit pheromone on the target entity (if specified).
            3. Create a neural signal with the mapped priority.
            4. Transmit the signal through the network.
            5. Return the ``TransmitResult`` from the conduction engine.

        Parameters
        ----------
        event_type : str
            Semantic event name (e.g. ``"fraud_alert"``, ``"tax_deadline"``).
            Mapped to a pheromone type via ``EVENT_TO_PHEROMONE``.
        payload : dict
            Arbitrary data cargo to carry with the event.
        priority : str
            Signal priority: ``"CRITICAL"``, ``"HIGH"``, ``"NORMAL"``,
            or ``"LOW"``.  Determines conduction mode.
        source_node : str
            Originating node in the neural network topology.
        target_entity_type : str, optional
            Entity type for pheromone targeting (e.g. ``"booking"``).
        target_entity_id : int, optional
            Entity database ID for pheromone targeting.
        db : AsyncSession, optional
            Database session for persistence.  If ``None``, pheromone
            deposits and signal logs are in-memory only.

        Returns
        -------
        TransmitResult
            Outcome of neural signal transmission.
        """
        self._emit_count += 1

        # 1. Map event type to pheromone type
        pheromone_type = EVENT_TO_PHEROMONE.get(
            event_type, PheromoneType.STATE_RESIDUE
        )

        # 2. Deposit pheromone on target entity
        if target_entity_type is not None and target_entity_id is not None:
            pheromone = create_pheromone(
                ptype=pheromone_type,
                intensity=min(1.0, payload.get("score", 0.8)),
                position=f"{target_entity_type}:{target_entity_id}",
                source_agent=source_node,
                target_entity_type=target_entity_type,
                target_entity_id=target_entity_id,
                payload=payload,
                decay_rate=settings.pheromone_default_decay_rate,
            )
            await self.env.deposit(pheromone, db=db)

        # 3. Resolve signal priority
        try:
            signal_priority = SignalPriority(priority.lower())
        except ValueError:
            signal_priority = SignalPriority.NORMAL

        # 4. Create and transmit neural signal
        signal = create_signal(
            signal_type=event_type,
            priority=signal_priority,
            payload=payload,
            intensity=min(1.0, payload.get("score", 0.8)),
            source_node=source_node,
        )
        result = await self.network.transmit(signal, db=db)

        logger.info(
            "EventBus emit #%d: type=%s priority=%s propagated=%s path=%s",
            self._emit_count,
            event_type,
            priority,
            result.propagated,
            result.path_taken,
        )

        return result

    def get_stats(self) -> dict:
        """Return bus-level statistics for monitoring."""
        return {
            "total_events_emitted": self._emit_count,
            "pheromone_deposits": len(self.env._deposits),
            "network_nodes": len(self.network.nodes),
            "network_pathways": len(self.network.pathways),
            "myelinated_pathways": sum(
                1 for pw in self.network.pathways.values() if pw.is_myelinated
            ),
            "aweb_veins": len(self.aweb.veins),
        }


# ---------------------------------------------------------------------------
# 8. Neural Tick -- One Heartbeat of the Organism
# ---------------------------------------------------------------------------

async def run_neural_tick(db: AsyncSession | None = None) -> dict:
    """Execute one heartbeat of the living organism.

    A tick performs these operations in order:

        1. **Evaporate** -- remove expired pheromones from the environment.
        2. **Convert** -- turn strong pheromones into neural signals.
        3. **Transmit** -- propagate all pending signals through the network.
        4. **Feedback** -- deposit pheromones from signal amplification.
        5. **Myelinate** -- strengthen pathways with heavy pheromone traffic.
        6. **Persist** -- flush state to the database (if *db* provided).

    Returns a tick summary dict with counts for each operation.
    """
    env = get_environment()
    network = get_network()

    # 1. Evaporate old pheromones
    evaporated = env.evaporate()

    # 2. Convert strong pheromones to signals
    signals_created = 0
    pending_signals: list[NeuralSignal] = []

    for pheromone in list(env._deposits):
        signal = await pheromone_to_signal(pheromone)
        if signal is not None:
            pending_signals.append(signal)
            signals_created += 1

    # 3. Transmit all pending signals
    signals_propagated = 0
    amplified_nodes: list[tuple[NeuralSignal, str]] = []

    for signal in pending_signals:
        result = await network.transmit(signal, db=db)
        if result.propagated:
            signals_propagated += 1
            # Track nodes that amplified the signal for feedback
            for node_id in result.path_taken[1:]:
                amplified_nodes.append((signal, node_id))

    # 4. Deposit feedback pheromones from signal amplification
    for signal, node_id in amplified_nodes:
        feedback = await signal_to_pheromone(signal, node_id)
        await env.deposit(feedback, db=db)

    # 5. Auto-myelinate pathways based on pheromone traffic
    pathways_myelinated = await auto_myelinate_from_trails(env, network)

    # Also run the conduction engine's own auto-myelination
    await network.auto_myelinate(threshold=settings.myelination_threshold)

    # 6. Persist state to DB if session provided
    if db is not None:
        await env.persist(db)
        await network.persist(db)

    summary = {
        "evaporated": evaporated,
        "signals_created": signals_created,
        "signals_propagated": signals_propagated,
        "pathways_myelinated": pathways_myelinated,
        "feedback_deposits": len(amplified_nodes),
        "active_pheromones": len(env._deposits),
        "timestamp": time.time(),
    }

    logger.info(
        "Neural tick: evaporated=%d created=%d propagated=%d myelinated=%d",
        evaporated,
        signals_created,
        signals_propagated,
        pathways_myelinated,
    )

    return summary


# ---------------------------------------------------------------------------
# 9. Module-level Singleton
# ---------------------------------------------------------------------------

_bus: NeuralEventBus | None = None


def get_event_bus() -> NeuralEventBus:
    """Return the global NeuralEventBus singleton.

    Creates a bus backed by the default singletons on first access.
    For explicit initialization with a database session, call
    ``initialize_neural_system()`` instead.
    """
    global _bus
    if _bus is None:
        _bus = NeuralEventBus(
            env=get_environment(),
            network=get_network(),
            aweb=get_aweb(),
        )
    return _bus


# ---------------------------------------------------------------------------
# 10. Full System Bootstrap
# ---------------------------------------------------------------------------

async def initialize_neural_system(
    db: AsyncSession | None = None,
) -> dict:
    """Bootstrap the entire neural organism.

    Creates all three subsystems, wires them together, optionally loads
    persisted state from the database, and returns all singletons in a
    dict for inspection or testing.

    Steps:
        1. Create PheromoneEnvironment singleton
        2. Create NeuralNetwork with default financial topology
        3. Initialize AWEB with default veins
        4. Create the unified NeuralEventBus
        5. Load persisted state from DB (if *db* provided)

    Returns
    -------
    dict
        Keys: ``"env"``, ``"network"``, ``"aweb"``, ``"bus"``
    """
    global _bus

    # 1. Pheromone environment
    env = get_environment()

    # 2. Neural network with pre-wired financial topology
    network = create_default_financial_network()

    # 3. AWEB vascular system
    aweb = await initialize_aweb(db=None)

    # 4. Create the event bus
    _bus = NeuralEventBus(env=env, network=network, aweb=aweb)

    # 5. Load persisted state from DB
    if db is not None:
        try:
            await env.load(db)
            logger.info("Pheromone environment loaded from database")
        except Exception as exc:
            logger.warning("Could not load pheromone state: %s", exc)

        try:
            await network.load(db)
            logger.info("Neural network loaded from database")
        except Exception as exc:
            logger.warning("Could not load neural network state: %s", exc)

        try:
            await aweb.load(db)
            logger.info("AWEB loaded from database")
        except Exception as exc:
            logger.warning("Could not load AWEB state: %s", exc)

    node_count = len(network.nodes)
    pathway_count = len(network.pathways)
    myelinated = sum(1 for pw in network.pathways.values() if pw.is_myelinated)
    vein_count = len(aweb.veins)

    logger.info(
        "Neural organism initialized: %d nodes, %d pathways (%d myelinated), "
        "%d veins, event bus active",
        node_count,
        pathway_count,
        myelinated,
        vein_count,
    )

    return {
        "env": env,
        "network": network,
        "aweb": aweb,
        "bus": _bus,
    }

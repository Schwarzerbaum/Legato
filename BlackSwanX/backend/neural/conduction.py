"""Saltatory Conduction Engine -- Myelinated Neural Network for BlackSwanX.

Models biological signal transmission in a financial organism:
  - CRITICAL signals (fraud, tax deadlines) jump between Nodes of Ranvier
    via myelinated pathways, skipping intermediate nodes entirely.
  - Routine signals traverse every node sequentially, each applying its
    threshold gate and amplification factor.
  - Pathways earn myelination through repeated use with high-priority
    signals -- the organism learns which routes matter.

Biological analogy:
  Myelinated axon:   [Node]----myelin----[Node]----myelin----[Node]
  Signal jumps:       src =========================> target  (saltatory)
  Unmyelinated axon: [Node]-[Node]-[Node]-[Node]-[Node]
  Signal crawls:      src -> n1 -> n2 -> n3 -> target       (continuous)
"""

from __future__ import annotations

import time
import uuid
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import NeuralPathway, NeuralSignalLog

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1. Signal Priority
# ---------------------------------------------------------------------------

class SignalPriority(str, Enum):
    """Priority tiers for neural signals.

    CRITICAL -- Tax deadline, fraud detected, apoptosis trigger.
                Uses myelinated (saltatory) conduction: signal jumps
                directly to target, skipping all intermediate nodes.
    HIGH     -- Anomaly found, large transaction.
                Prefers myelinated paths, falls back to unmyelinated.
    NORMAL   -- Routine booking processed.
                Unmyelinated continuous conduction only.
    LOW      -- Informational only.
                Unmyelinated continuous conduction only.
    """

    CRITICAL = "critical"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


PRIORITY_VALUES: dict[str, int] = {
    "critical": 4,
    "high": 3,
    "normal": 2,
    "low": 1,
}


# ---------------------------------------------------------------------------
# 2. NeuralSignal
# ---------------------------------------------------------------------------

@dataclass
class NeuralSignal:
    """A signal propagating through the neural network.

    Attributes:
        id:          Unique identifier (uuid4 hex).
        signal_type: Semantic label -- e.g. ``fraud_alert``, ``tax_deadline``.
        priority:    Determines conduction mode (saltatory vs continuous).
        payload:     Arbitrary data cargo carried by the signal.
        intensity:   Signal strength 0.0-1.0.  Nodes gate on this value
                     and amplify it when the signal passes through.
        source_node: Originating node identifier.
        path_taken:  Ordered list of node IDs the signal has visited.
        created_at:  Unix timestamp of signal creation.
    """

    signal_type: str
    priority: SignalPriority
    payload: dict
    intensity: float
    source_node: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    path_taken: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)


# ---------------------------------------------------------------------------
# 3. NodeOfRanvier
# ---------------------------------------------------------------------------

@dataclass
class NodeOfRanvier:
    """A gating node in the neural network.

    In biology, Nodes of Ranvier are gaps in the myelin sheath where
    action potentials are regenerated.  Here, each node decides whether
    to propagate or absorb a signal based on intensity thresholds.

    Attributes:
        id:                    Node / agent identifier.
        threshold:             Minimum intensity required to pass (0.0-1.0).
        amplification_factor:  Multiplier applied to intensity on passage.
        refractory_period:     Cooldown seconds after firing.
        refractory_until:      Absolute time when the node can fire again.
        connections:           IDs of downstream nodes.
    """

    id: str
    threshold: float = 0.3
    amplification_factor: float = 1.2
    refractory_period: float = 2.0
    refractory_until: float = 0.0
    connections: list[str] = field(default_factory=list)

    def can_fire(self) -> bool:
        """Return True if the refractory period has elapsed."""
        return time.time() >= self.refractory_until

    def process_signal(self, signal: NeuralSignal) -> Optional[NeuralSignal]:
        """Gate and optionally amplify a signal.

        Returns the (modified) signal if it passes, or ``None`` if it
        is absorbed by this node (too weak or node in refractory).
        """
        if not self.can_fire():
            logger.debug(
                "Node %s in refractory -- signal %s absorbed", self.id, signal.id
            )
            return None

        if signal.intensity < self.threshold:
            logger.debug(
                "Node %s threshold %.2f > signal intensity %.2f -- signal dies",
                self.id,
                self.threshold,
                signal.intensity,
            )
            return None

        # Amplify, cap at 1.0
        signal.intensity = min(signal.intensity * self.amplification_factor, 1.0)
        signal.path_taken.append(self.id)
        self.refractory_until = time.time() + self.refractory_period
        return signal

    def reset(self) -> None:
        """Clear refractory state so the node can fire immediately."""
        self.refractory_until = 0.0


# ---------------------------------------------------------------------------
# 4. PathwayInfo
# ---------------------------------------------------------------------------

@dataclass
class PathwayInfo:
    """In-memory representation of a pathway between two nodes.

    Attributes:
        from_node:         Source node identifier.
        to_node:           Target node identifier.
        is_myelinated:     Derived: True when ``myelination_score >= 0.7``.
        myelination_score: Accumulated score 0.0-1.0.
        signal_count:      Total signals carried on this pathway.
        avg_priority:      Running average of signal priority values.
        last_signal_at:    Unix timestamp of the most recent signal.
    """

    from_node: str
    to_node: str
    is_myelinated: bool = False
    myelination_score: float = 0.0
    signal_count: int = 0
    avg_priority: float = 0.0
    last_signal_at: float = 0.0


# ---------------------------------------------------------------------------
# 5. TransmitResult
# ---------------------------------------------------------------------------

@dataclass
class TransmitResult:
    """Outcome of a signal transmission through the network.

    Attributes:
        propagated:      True if the signal reached at least one target.
        path_taken:      Ordered node IDs the signal traversed.
        final_intensity: Intensity at the end of propagation.
        stopped_at:      Node ID where the signal died, or None.
        signal_type:     Echo of the original signal type.
        priority:        Echo of the original signal priority.
    """

    propagated: bool
    path_taken: list[str]
    final_intensity: float
    stopped_at: Optional[str]
    signal_type: str
    priority: SignalPriority


# ---------------------------------------------------------------------------
# 6. NeuralNetwork
# ---------------------------------------------------------------------------

class NeuralNetwork:
    """The full neural network -- saltatory and continuous conduction.

    Manages nodes, pathways, signal transmission, adaptive myelination,
    and persistence to the database.
    """

    def __init__(self) -> None:
        self.nodes: dict[str, NodeOfRanvier] = {}
        self.pathways: dict[tuple[str, str], PathwayInfo] = {}
        # Token savings tracking
        self.tokens_saved: int = 0  # Estimated tokens saved via myelination
        self.tokens_spent: int = 0  # Estimated tokens spent on signal processing

    # -- Registration -------------------------------------------------------

    def register_node(self, node: NodeOfRanvier) -> None:
        """Add a single node to the network."""
        self.nodes[node.id] = node

    def register_nodes_from_list(
        self, node_ids: list[str], threshold: float = 0.3
    ) -> None:
        """Batch-create nodes with identical threshold."""
        for nid in node_ids:
            self.nodes[nid] = NodeOfRanvier(id=nid, threshold=threshold)

    def connect(self, from_node: str, to_node: str) -> None:
        """Create a pathway between two registered nodes.

        Also updates the source node's connection list.
        """
        key = (from_node, to_node)
        if key not in self.pathways:
            self.pathways[key] = PathwayInfo(from_node=from_node, to_node=to_node)
        if from_node in self.nodes and to_node not in self.nodes[from_node].connections:
            self.nodes[from_node].connections.append(to_node)

    # -- Transmission -------------------------------------------------------

    async def transmit(
        self,
        signal: NeuralSignal,
        db: Optional[AsyncSession] = None,
    ) -> TransmitResult:
        """Transmit a signal through the network.

        Conduction mode depends on signal priority:

        CRITICAL
            Saltatory conduction -- signal jumps directly from the source
            to every connected node that has a myelinated pathway.
            Intermediate nodes are skipped entirely.

        HIGH
            Prefers myelinated pathways where available.  Falls back to
            unmyelinated (continuous) conduction for pathways that have
            not yet earned myelination.

        NORMAL / LOW
            Continuous conduction only -- signal must pass through each
            intermediate Node of Ranvier in sequence.  Each node applies
            its threshold gate and amplification factor.
        """
        source = signal.source_node
        signal.path_taken = [source]
        propagated = False
        stopped_at: Optional[str] = None

        if signal.priority == SignalPriority.CRITICAL:
            propagated, stopped_at = await self._transmit_saltatory(
                signal, source, myelinated_only=True
            )
            # Saltatory jump: estimate tokens saved by skipping intermediate nodes
            source_node = self.nodes.get(source)
            if source_node is not None:
                skipped = [
                    tid for tid in source_node.connections
                    if self.pathways.get((source, tid), PathwayInfo(source, tid)).is_myelinated
                ]
                self.tokens_saved += len(skipped) * 500
        elif signal.priority == SignalPriority.HIGH:
            propagated, stopped_at = await self._transmit_saltatory(
                signal, source, myelinated_only=False
            )
            # HIGH signals: myelinated paths save tokens, unmyelinated spend
            source_node = self.nodes.get(source)
            if source_node is not None:
                for tid in source_node.connections:
                    pw = self.pathways.get((source, tid))
                    if pw is not None and pw.is_myelinated:
                        self.tokens_saved += 500
                    else:
                        self.tokens_spent += 500
        else:
            propagated, stopped_at = await self._transmit_continuous(signal, source)
            # Continuous conduction: every node traversed costs tokens
            path_len = len(signal.path_taken)
            self.tokens_spent += path_len * 500

        # Persist signal log and update pathway stats
        if db is not None:
            await self._log_signal(db, signal, propagated, stopped_at)
            await self._update_pathway_stats(db, signal)

        return TransmitResult(
            propagated=propagated,
            path_taken=list(signal.path_taken),
            final_intensity=signal.intensity,
            stopped_at=stopped_at,
            signal_type=signal.signal_type,
            priority=signal.priority,
        )

    async def _transmit_saltatory(
        self,
        signal: NeuralSignal,
        source: str,
        *,
        myelinated_only: bool,
    ) -> tuple[bool, Optional[str]]:
        """Saltatory conduction -- jump directly to connected nodes.

        When *myelinated_only* is True (CRITICAL), only myelinated
        pathways are used.  When False (HIGH), unmyelinated pathways
        also participate but the signal is routed through continuous
        conduction on those segments.
        """
        propagated = False
        stopped_at: Optional[str] = None
        source_node = self.nodes.get(source)

        if source_node is None:
            return False, source

        targets = source_node.connections
        for target_id in targets:
            key = (source, target_id)
            pathway = self.pathways.get(key)
            target_node = self.nodes.get(target_id)
            if target_node is None:
                continue

            if pathway is not None and pathway.is_myelinated:
                # Saltatory jump -- skip intermediate processing
                result = target_node.process_signal(signal)
                if result is not None:
                    propagated = True
                else:
                    stopped_at = target_id
            elif not myelinated_only:
                # Fall back to continuous for unmyelinated pathways
                result = target_node.process_signal(signal)
                if result is not None:
                    propagated = True
                else:
                    stopped_at = target_id
            # If myelinated_only and pathway is not myelinated, skip it

        return propagated, stopped_at

    async def _transmit_continuous(
        self,
        signal: NeuralSignal,
        source: str,
    ) -> tuple[bool, Optional[str]]:
        """Continuous conduction -- traverse each node sequentially.

        The signal walks from the source through each connected node in
        a breadth-first manner.  Each Node of Ranvier applies its
        threshold gate; if the signal falls below threshold it dies.
        """
        visited: set[str] = {source}
        queue: list[str] = list(self.nodes[source].connections) if source in self.nodes else []
        propagated = False
        stopped_at: Optional[str] = None

        while queue:
            current_id = queue.pop(0)
            if current_id in visited:
                continue
            visited.add(current_id)

            node = self.nodes.get(current_id)
            if node is None:
                continue

            result = node.process_signal(signal)
            if result is None:
                stopped_at = current_id
                break

            propagated = True
            # Continue to next connected nodes
            for next_id in node.connections:
                if next_id not in visited:
                    queue.append(next_id)

        return propagated, stopped_at

    # -- Logging & Stats ----------------------------------------------------

    async def _log_signal(
        self,
        db: AsyncSession,
        signal: NeuralSignal,
        propagated: bool,
        stopped_at: Optional[str],
    ) -> None:
        """Persist a signal transmission record to the database."""
        # Find the pathway id if one exists for the source -> first target
        pathway_id: Optional[int] = None
        if len(signal.path_taken) >= 2:
            key = (signal.path_taken[0], signal.path_taken[1])
            pathway = self.pathways.get(key)
            if pathway is not None:
                result = await db.execute(
                    select(NeuralPathway.id).where(
                        NeuralPathway.from_node == key[0],
                        NeuralPathway.to_node == key[1],
                    )
                )
                row = result.scalar_one_or_none()
                if row is not None:
                    pathway_id = row

        log_entry = NeuralSignalLog(
            pathway_id=pathway_id,
            signal_type=signal.signal_type,
            priority=signal.priority.value.upper(),
            payload=signal.payload,
            intensity=signal.intensity,
            propagated=propagated,
            stopped_at_node=stopped_at,
            apoptosis_triggered=signal.payload.get("apoptosis", False)
            if isinstance(signal.payload, dict)
            else False,
        )
        db.add(log_entry)
        await db.flush()

    async def _update_pathway_stats(
        self,
        db: AsyncSession,
        signal: NeuralSignal,
    ) -> None:
        """Increment signal count and recalculate average priority on pathways."""
        priority_val = PRIORITY_VALUES.get(signal.priority.value, 2)
        now = time.time()

        for i in range(len(signal.path_taken) - 1):
            key = (signal.path_taken[i], signal.path_taken[i + 1])
            pw = self.pathways.get(key)
            if pw is None:
                continue

            # Recalculate running average
            old_total = pw.avg_priority * pw.signal_count
            pw.signal_count += 1
            pw.avg_priority = (old_total + priority_val) / pw.signal_count
            pw.last_signal_at = now

            # Sync to database
            await db.execute(
                update(NeuralPathway)
                .where(
                    NeuralPathway.from_node == key[0],
                    NeuralPathway.to_node == key[1],
                )
                .values(
                    signal_count=pw.signal_count,
                    avg_priority=pw.avg_priority,
                    last_signal_at=None,  # Use DB-side datetime
                )
            )
        await db.flush()

    # -- Myelination --------------------------------------------------------

    async def myelinate_pathway(
        self,
        from_node: str,
        to_node: str,
        increment: float = 0.1,
    ) -> None:
        """Increase myelination score for a pathway.

        When the score crosses 0.7 the pathway is marked myelinated and
        future CRITICAL/HIGH signals will use saltatory conduction.
        """
        key = (from_node, to_node)
        pw = self.pathways.get(key)
        if pw is None:
            logger.warning("Cannot myelinate unknown pathway %s -> %s", from_node, to_node)
            return

        pw.myelination_score = min(pw.myelination_score + increment, 1.0)
        if pw.myelination_score >= 0.7:
            pw.is_myelinated = True
            logger.info(
                "Pathway %s -> %s is now MYELINATED (score=%.2f)",
                from_node,
                to_node,
                pw.myelination_score,
            )

    async def auto_myelinate(self, threshold: int = 10) -> None:
        """Scan pathways and auto-myelinate those with heavy high-priority traffic.

        A pathway qualifies when:
          - ``signal_count >= threshold``
          - ``avg_priority >= 2.5`` (average at least HIGH)

        This is adaptive myelination -- the organism learns which routes
        carry critical information and optimizes them for speed.
        """
        for key, pw in self.pathways.items():
            if pw.signal_count >= threshold and pw.avg_priority >= 2.5:
                await self.myelinate_pathway(key[0], key[1])

    # -- Queries ------------------------------------------------------------

    def get_myelinated_pathways(self) -> list[PathwayInfo]:
        """Return all pathways that have earned myelination."""
        return [pw for pw in self.pathways.values() if pw.is_myelinated]

    def get_network_state(self) -> dict:
        """Full topology snapshot for visualization and debugging.

        Returns a dict with ``nodes``, ``pathways``, and ``stats`` keys.
        """
        return {
            "nodes": {
                nid: {
                    "threshold": node.threshold,
                    "amplification_factor": node.amplification_factor,
                    "connections": node.connections,
                    "can_fire": node.can_fire(),
                    "refractory_until": node.refractory_until,
                }
                for nid, node in self.nodes.items()
            },
            "pathways": {
                f"{pw.from_node}->{pw.to_node}": {
                    "is_myelinated": pw.is_myelinated,
                    "myelination_score": round(pw.myelination_score, 3),
                    "signal_count": pw.signal_count,
                    "avg_priority": round(pw.avg_priority, 2),
                    "last_signal_at": pw.last_signal_at,
                }
                for pw in self.pathways.values()
            },
            "stats": {
                "total_nodes": len(self.nodes),
                "total_pathways": len(self.pathways),
                "myelinated_pathways": sum(
                    1 for pw in self.pathways.values() if pw.is_myelinated
                ),
                "total_signals": sum(
                    pw.signal_count for pw in self.pathways.values()
                ),
                "tokens_saved": self.tokens_saved,
                "tokens_spent": self.tokens_spent,
            },
        }

    def get_efficiency_report(self) -> dict:
        """Token efficiency report -- how much myelination is saving.

        Returns a dict with tokens_saved, tokens_spent, efficiency percentage,
        and pathway counts for dashboard display.
        """
        total = self.tokens_saved + self.tokens_spent
        efficiency = self.tokens_saved / total if total > 0 else 0
        return {
            "tokens_saved": self.tokens_saved,
            "tokens_spent": self.tokens_spent,
            "total_processed": total,
            "efficiency_pct": round(efficiency * 100, 1),
            "myelinated_pathways": len(self.get_myelinated_pathways()),
            "total_pathways": len(self.pathways),
        }

    # -- Persistence --------------------------------------------------------

    async def persist(self, db: AsyncSession) -> None:
        """Save all pathways to the NeuralPathway table (upsert semantics).

        Uses from_node + to_node as the natural key.  Existing rows are
        updated; new pathways are inserted.
        """
        for key, pw in self.pathways.items():
            result = await db.execute(
                select(NeuralPathway).where(
                    NeuralPathway.from_node == key[0],
                    NeuralPathway.to_node == key[1],
                )
            )
            existing = result.scalar_one_or_none()

            if existing is not None:
                existing.pathway_type = "myelinated" if pw.is_myelinated else "unmyelinated"
                existing.myelination_score = pw.myelination_score
                existing.signal_count = pw.signal_count
                existing.avg_priority = pw.avg_priority
            else:
                db.add(
                    NeuralPathway(
                        from_node=key[0],
                        to_node=key[1],
                        pathway_type="myelinated" if pw.is_myelinated else "unmyelinated",
                        myelination_score=pw.myelination_score,
                        signal_count=pw.signal_count,
                        avg_priority=pw.avg_priority,
                    )
                )

        await db.flush()

    async def load(self, db: AsyncSession) -> None:
        """Load pathways from the database and reconstruct network state.

        Nodes referenced by pathways but not yet registered are created
        automatically with default thresholds.
        """
        result = await db.execute(select(NeuralPathway))
        rows = result.scalars().all()

        for row in rows:
            key = (row.from_node, row.to_node)
            pw = PathwayInfo(
                from_node=row.from_node,
                to_node=row.to_node,
                is_myelinated=row.myelination_score >= 0.7,
                myelination_score=row.myelination_score,
                signal_count=row.signal_count,
                avg_priority=row.avg_priority,
                last_signal_at=(
                    row.last_signal_at.timestamp() if row.last_signal_at else 0.0
                ),
            )
            self.pathways[key] = pw

            # Auto-register nodes referenced by persisted pathways
            for nid in (row.from_node, row.to_node):
                if nid not in self.nodes:
                    self.nodes[nid] = NodeOfRanvier(id=nid)

            # Rebuild connection adjacency
            if row.from_node in self.nodes:
                if row.to_node not in self.nodes[row.from_node].connections:
                    self.nodes[row.from_node].connections.append(row.to_node)

        logger.info(
            "Loaded %d pathways (%d myelinated) across %d nodes",
            len(self.pathways),
            sum(1 for pw in self.pathways.values() if pw.is_myelinated),
            len(self.nodes),
        )


# ---------------------------------------------------------------------------
# 7. Module-level singleton
# ---------------------------------------------------------------------------

_network: Optional[NeuralNetwork] = None


def get_network() -> NeuralNetwork:
    """Return the module-level singleton NeuralNetwork instance.

    Creates one on first access.  Use ``create_default_financial_network``
    to get a pre-wired topology instead.
    """
    global _network
    if _network is None:
        _network = NeuralNetwork()
    return _network


# ---------------------------------------------------------------------------
# 8. Helper functions
# ---------------------------------------------------------------------------

def create_signal(
    signal_type: str,
    priority: SignalPriority,
    payload: dict,
    intensity: float,
    source_node: str,
) -> NeuralSignal:
    """Convenience constructor for NeuralSignal."""
    return NeuralSignal(
        signal_type=signal_type,
        priority=priority,
        payload=payload,
        intensity=max(0.0, min(intensity, 1.0)),
        source_node=source_node,
    )


def create_default_financial_network() -> NeuralNetwork:
    """Pre-wire the BlackSwanX financial organism neural network.

    Topology mirrors the accounting organism's data flow::

        receipt_scanner -----> datev_parser --------> bookkeeping_engine
                                                           |
                               ust_va_calculator <---------+
                                                           |
                               fraud_detector <------------+
                                   |
                               audit_risk <----------------+
                                                           |
                               tax_optimizer <-------------+
                                   |
                               cashflow_predictor <--------+
                                                           |
                               regulatory_change ----------+
                                                           |
                               nexus_orchestrator <--------+-- (hub)

    The nexus_orchestrator acts as the central nervous system hub --
    all specialist nodes connect to it for cross-domain coordination.
    """
    global _network

    net = NeuralNetwork()

    # Register all organism nodes
    node_ids = [
        "fraud_detector",
        "tax_optimizer",
        "cashflow_predictor",
        "audit_risk",
        "regulatory_change",
        "receipt_scanner",
        "bookkeeping_engine",
        "datev_parser",
        "ust_va_calculator",
        "nexus_orchestrator",
    ]
    net.register_nodes_from_list(node_ids, threshold=0.3)

    # --- Data ingestion pipeline ---
    net.connect("receipt_scanner", "datev_parser")
    net.connect("datev_parser", "bookkeeping_engine")

    # --- Bookkeeping fans out to specialists ---
    net.connect("bookkeeping_engine", "fraud_detector")
    net.connect("bookkeeping_engine", "ust_va_calculator")
    net.connect("bookkeeping_engine", "tax_optimizer")
    net.connect("bookkeeping_engine", "cashflow_predictor")
    net.connect("bookkeeping_engine", "audit_risk")

    # --- Specialist cross-links ---
    net.connect("fraud_detector", "audit_risk")
    net.connect("tax_optimizer", "ust_va_calculator")
    net.connect("regulatory_change", "bookkeeping_engine")
    net.connect("regulatory_change", "tax_optimizer")
    net.connect("regulatory_change", "ust_va_calculator")

    # --- Nexus orchestrator hub (bidirectional with all nodes) ---
    for nid in node_ids:
        if nid != "nexus_orchestrator":
            net.connect(nid, "nexus_orchestrator")
            net.connect("nexus_orchestrator", nid)

    _network = net
    return net

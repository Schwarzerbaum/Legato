"""Neural Communication API Router — The organism's nervous system dashboard.

Endpoints for:
- Pheromone heatmap (Living Ledger visualization)
- Neural network topology (nodes, pathways, myelination)
- Signal history
- AWEB vein health
- Apoptosis event log
- Manual neural tick
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.db import get_db
from backend.database.models import (
    PheromoneDeposit, NeuralPathway, NeuralSignalLog, AWEBVein, ApoptosisLog,
)

router = APIRouter()


# ── PHEROMONES (Living Ledger) ───────────────────────────────

@router.get("/pheromones")
async def get_pheromone_heatmap(db: AsyncSession = Depends(get_db)):
    """Get current pheromone heatmap for visualization."""
    try:
        from backend.neural.pheromones import get_environment
        env = get_environment()
        await env.load(db)
        return {
            "heatmap": env.get_heatmap(),
            "entity_heatmap": env.get_entity_heatmap(),
            "total_deposits": len(env._deposits),
        }
    except Exception as e:
        return {"heatmap": {}, "entity_heatmap": {}, "error": str(e)}


@router.get("/pheromones/{position}")
async def get_pheromones_at_position(position: str, db: AsyncSession = Depends(get_db)):
    """Get all pheromones at a specific node/position."""
    try:
        from backend.neural.pheromones import get_environment
        env = get_environment()
        await env.load(db)
        pheromones = env.sense(position=position)
        return [
            {
                "type": p.type.value if hasattr(p.type, "value") else str(p.type),
                "intensity": p.current_intensity,
                "source_agent": p.source_agent,
                "target_entity_type": p.target_entity_type,
                "target_entity_id": p.target_entity_id,
                "payload": p.payload,
            }
            for p in pheromones
        ]
    except Exception as e:
        return {"error": str(e)}


# ── NEURAL NETWORK ───────────────────────────────────────────

@router.get("/network")
async def get_network_topology(db: AsyncSession = Depends(get_db)):
    """Get full neural network topology for D3 visualization."""
    try:
        from backend.neural.conduction import get_network
        network = get_network()
        await network.load(db)
        return network.get_network_state()
    except Exception as e:
        return {"nodes": [], "pathways": [], "error": str(e)}


@router.get("/pathways/myelinated")
async def get_myelinated_pathways(db: AsyncSession = Depends(get_db)):
    """Get all myelinated (high-speed) pathways."""
    try:
        from backend.neural.conduction import get_network
        network = get_network()
        await network.load(db)
        myelinated = network.get_myelinated_pathways()
        return [
            {
                "from_node": p.from_node,
                "to_node": p.to_node,
                "myelination_score": p.myelination_score,
                "signal_count": p.signal_count,
                "avg_priority": p.avg_priority,
            }
            for p in myelinated
        ]
    except Exception as e:
        return {"error": str(e)}


# ── SIGNAL HISTORY ───────────────────────────────────────────

@router.get("/signals/recent")
async def get_recent_signals(limit: int = 50, db: AsyncSession = Depends(get_db)):
    """Get recent neural signal transmissions."""
    result = await db.execute(
        select(NeuralSignalLog)
        .order_by(NeuralSignalLog.created_at.desc())
        .limit(limit)
    )
    signals = result.scalars().all()
    return [
        {
            "id": s.id,
            "signal_type": s.signal_type,
            "priority": s.priority,
            "intensity": s.intensity,
            "propagated": s.propagated,
            "stopped_at_node": s.stopped_at_node,
            "apoptosis_triggered": s.apoptosis_triggered,
            "payload": s.payload,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s in signals
    ]


# ── AWEB (Vascular System) ──────────────────────────────────

@router.get("/aweb")
async def get_aweb_health(db: AsyncSession = Depends(get_db)):
    """Get AWEB vein health report."""
    try:
        from backend.neural.aweb import get_aweb
        aweb = get_aweb()
        await aweb.load(db)
        return aweb.get_health_report()
    except Exception as e:
        return {"error": str(e), "total_veins": 0}


# ── APOPTOSIS LOG ───────────────────────────────────────────

@router.get("/apoptosis")
async def get_apoptosis_log(limit: int = 20, db: AsyncSession = Depends(get_db)):
    """Get apoptosis (immune system kill switch) event log."""
    result = await db.execute(
        select(ApoptosisLog)
        .order_by(ApoptosisLog.timestamp.desc())
        .limit(limit)
    )
    events = result.scalars().all()
    return [
        {
            "id": e.id,
            "entity_type": e.entity_type,
            "entity_id": e.entity_id,
            "trigger_reason": e.trigger_reason,
            "consensus_score": e.consensus_score,
            "threshold_required": e.threshold_required,
            "agents_involved": e.agents_involved,
            "timestamp": e.timestamp.isoformat() if e.timestamp else None,
        }
        for e in events
    ]


# ── NEURAL TICK (Manual Trigger) ─────────────────────────────

@router.post("/tick")
async def manual_neural_tick(db: AsyncSession = Depends(get_db)):
    """Manually trigger one heartbeat of the organism."""
    try:
        from backend.neural.integration import run_neural_tick
        result = await run_neural_tick(db)
        return result
    except Exception as e:
        return {"error": str(e)}


# ── REGULATORY SCAN ─────────────────────────────────────────

@router.post("/regulatory-scan")
async def regulatory_scan(db: AsyncSession = Depends(get_db)):
    """Run BMF/BFH crawler and deposit REGULATORY_WIND pheromones."""
    from backend.crawler.bmf import crawl_regulatory_updates
    from backend.neural.pheromones import get_environment, PheromoneType, create_pheromone

    updates = await crawl_regulatory_updates()
    env = get_environment()

    for update in updates[:10]:  # Top 10 most relevant
        p = create_pheromone(
            ptype=PheromoneType.REGULATORY_WIND,
            intensity=0.7,
            position="regulatory_change",
            source_agent="bmf_crawler",
            payload={
                "title": update.get("content", "")[:200],
                "url": update.get("url", ""),
                "platform": update.get("platform", ""),
            },
        )
        await env.deposit(p, db)

    await env.persist(db)
    return {
        "updates_found": len(updates),
        "pheromones_deposited": min(len(updates), 10),
    }


# ── TOKEN EFFICIENCY ───────────────────────────────────────

@router.get("/efficiency")
async def get_efficiency():
    """Get token savings report from myelinated pathways."""
    from backend.neural.conduction import get_network
    network = get_network()
    return network.get_efficiency_report()


# ── STATS ────────────────────────────────────────────────────

@router.get("/stats")
async def get_neural_stats(db: AsyncSession = Depends(get_db)):
    """Get overall neural system statistics."""
    from sqlalchemy import func

    pheromone_count = (await db.execute(select(func.count(PheromoneDeposit.id)))).scalar_one()
    pathway_count = (await db.execute(select(func.count(NeuralPathway.id)))).scalar_one()
    myelinated_count = (await db.execute(
        select(func.count(NeuralPathway.id))
        .where(NeuralPathway.myelination_score >= 0.7)
    )).scalar_one()
    signal_count = (await db.execute(select(func.count(NeuralSignalLog.id)))).scalar_one()
    apoptosis_count = (await db.execute(select(func.count(ApoptosisLog.id)))).scalar_one()
    vein_count = (await db.execute(select(func.count(AWEBVein.id)))).scalar_one()

    return {
        "pheromone_deposits": pheromone_count,
        "neural_pathways": pathway_count,
        "myelinated_pathways": myelinated_count,
        "signals_transmitted": signal_count,
        "apoptosis_events": apoptosis_count,
        "aweb_veins": vein_count,
    }

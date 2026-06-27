"""Simulation endpoints — adversarial agents, kill-switch, black swans."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from backend.database.db import get_db
from backend.database.models import Topic, Simulation
from backend.simulation.kill_switch import run_kill_switch
from backend.simulation.blackswan import inject_black_swans, what_if
from backend.simulation.sona import record_feedback

router = APIRouter()


class SimulationCreate(BaseModel):
    topic_id: int
    rounds: int = 5


class SimulationResponse(BaseModel):
    id: int
    topic_id: int
    status: str
    total_rounds: int
    current_round: int

    model_config = {"from_attributes": True}


class FeedbackRequest(BaseModel):
    report_id: int
    accuracy_score: int  # 0-10
    feedback: str


class WhatIfRequest(BaseModel):
    prediction_context: str
    scenario: str


@router.post("/start", response_model=SimulationResponse)
async def start_simulation(req: SimulationCreate, db: AsyncSession = Depends(get_db)):
    topic = await db.get(Topic, req.topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    sim = Simulation(topic_id=req.topic_id, total_rounds=req.rounds)
    db.add(sim)
    topic.status = "simulating"
    await db.commit()
    await db.refresh(sim)

    # TODO: Launch full simulation pipeline in background
    return sim


@router.get("/{sim_id}", response_model=SimulationResponse)
async def get_simulation(sim_id: int, db: AsyncSession = Depends(get_db)):
    sim = await db.get(Simulation, sim_id)
    if not sim:
        raise HTTPException(status_code=404, detail="Simulation not found")
    return sim


@router.post("/kill-switch/{topic_id}")
async def narrative_kill_switch(topic_id: int, db: AsyncSession = Depends(get_db)):
    """Run the Narrative Kill-Switch stress test.

    Swarm A (Fans) vs Swarm B (Assassins) → Volatility Score.
    """
    topic = await db.get(Topic, topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    # For now, use topic query as context. When compression is done, use personas.
    result = await run_kill_switch(topic.query, f"Topic: {topic.query}")
    return result


@router.post("/black-swan")
async def run_black_swan(prediction_context: str = ""):
    """Inject Black Swan events to stress-test a prediction."""
    if not prediction_context:
        raise HTTPException(status_code=400, detail="prediction_context required")
    return await inject_black_swans(prediction_context)


@router.post("/what-if")
async def run_what_if(req: WhatIfRequest):
    """User-injected What-If scenario."""
    return await what_if(req.prediction_context, req.scenario)


@router.post("/feedback")
async def submit_feedback(req: FeedbackRequest, db: AsyncSession = Depends(get_db)):
    """Submit accuracy feedback for SONA self-optimization."""
    return await record_feedback(db, req.report_id, req.accuracy_score, req.feedback)

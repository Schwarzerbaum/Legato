"""Report endpoints — generate and retrieve Decision-Ready Maps."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from backend.database.db import get_db
from backend.database.models import Report

router = APIRouter()


class ReportResponse(BaseModel):
    id: int
    topic_id: int
    title: str | None
    content_md: str | None
    pressure_points: dict | None
    token_usage: dict | None

    model_config = {"from_attributes": True}


@router.post("/generate/{topic_id}")
async def generate_report(topic_id: int, db: AsyncSession = Depends(get_db)):
    """Generate a Decision-Ready Map for a completed simulation."""
    # TODO: Launch report generation
    return {"status": "generating", "topic_id": topic_id}


@router.get("/{report_id}", response_model=ReportResponse)
async def get_report(report_id: int, db: AsyncSession = Depends(get_db)):
    report = await db.get(Report, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


@router.get("/topic/{topic_id}", response_model=list[ReportResponse])
async def get_reports_for_topic(topic_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Report).where(Report.topic_id == topic_id).order_by(Report.created_at.desc())
    )
    return result.scalars().all()

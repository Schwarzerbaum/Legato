"""Analysis endpoints — topic creation, crawling, compression."""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from backend.database.db import get_db
from backend.database.models import Topic

router = APIRouter()


class TopicCreate(BaseModel):
    query: str


class TopicResponse(BaseModel):
    id: int
    query: str
    status: str

    model_config = {"from_attributes": True}


@router.post("/topics", response_model=TopicResponse)
async def create_topic(req: TopicCreate, db: AsyncSession = Depends(get_db)):
    topic = Topic(query=req.query)
    db.add(topic)
    await db.commit()
    await db.refresh(topic)
    return topic


@router.get("/topics", response_model=list[TopicResponse])
async def list_topics(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Topic).order_by(Topic.created_at.desc()))
    return result.scalars().all()


@router.get("/topics/{topic_id}", response_model=TopicResponse)
async def get_topic(topic_id: int, db: AsyncSession = Depends(get_db)):
    topic = await db.get(Topic, topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    return topic


@router.post("/topics/{topic_id}/crawl")
async def start_crawl(topic_id: int, db: AsyncSession = Depends(get_db)):
    """Start crawling data for a topic. Returns immediately, crawl runs in background."""
    topic = await db.get(Topic, topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    topic.status = "crawling"
    await db.commit()

    # TODO: Launch background crawl task
    return {"status": "crawling", "topic_id": topic_id}


@router.post("/topics/{topic_id}/compress")
async def start_compression(topic_id: int, db: AsyncSession = Depends(get_db)):
    """Run semantic compression on crawled data → Social Personas."""
    topic = await db.get(Topic, topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    topic.status = "analyzing"
    await db.commit()

    # TODO: Launch compression pipeline
    return {"status": "analyzing", "topic_id": topic_id}

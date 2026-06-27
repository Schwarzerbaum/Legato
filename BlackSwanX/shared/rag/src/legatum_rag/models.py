"""API contract shared by the backend, the orchestrator, and any future UI."""
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field
class IngestRequest(BaseModel):
    pdf_path: str
    title: str | None = None
class IngestResult(BaseModel):
    doc_id: str
    title: str
    pages: int
    entities: int = 0
    relations: int = 0
    okf_concept: str = ""
    note: str = ""
class SearchRequest(BaseModel):
    query: str
    k: int = 5
class PageHit(BaseModel):
    doc_id: str
    page: int
    score: float
    image_path: str = ""
    title: str = ""
class SearchResponse(BaseModel):
    query: str
    hits: list[PageHit] = Field(default_factory=list)
class Entity(BaseModel):
    name: str = Field(description="The entity's canonical name, e.g. 'BIM-Leitfaden 2.0'")
    type: str = Field(default="", description="Short category, e.g. 'standard', 'organization'")
    description: str = Field(default="", description="One-line description, grounded in text")
class Relation(BaseModel):
    source: str = Field(description="Name of the source entity")
    target: str = Field(description="Name of the target entity")
    type: str = Field(default="", description="Short relation type, e.g. 'part_of'")
    description: str = Field(default="", description="One-line description of relation")
class Harvest(BaseModel):
    """The structured output of one LLM extraction call over a window of text."""
    entities: list[Entity] = Field(default_factory=list)
    relations: list[Relation] = Field(default_factory=list)
    summary: str = Field(default="", description="2-3 sentence summary of this section")
class Mention(BaseModel):
    """An entity's provenance: it was seen on this page (within a doc)."""
    name_key: str
    page: int
class DocHarvest(BaseModel):
    """Merged result of a windowed harvest over a whole document."""
    entities: list[Entity] = Field(default_factory=list)
    relations: list[Relation] = Field(default_factory=list)
    mentions: list[Mention] = Field(default_factory=list)
    summary: str = ""
    windows: int = 0
    pages: int = 0
    merged: int = 0
class MergeGroup(BaseModel):
    """A set of entity names that denote the same real-world entity."""
    canonical: str = Field(description="The clearest name to keep for this entity")
    aliases: list[str] = Field(default_factory=list)
class Curation(BaseModel):
    """The GraphCurator's structured output — conservative duplicate merges."""
    merges: list[MergeGroup] = Field(default_factory=list)

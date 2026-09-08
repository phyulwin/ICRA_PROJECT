# backend/app/schemas/library.py
"""Firestore-backed Library reference and directing-board contracts."""

from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl

from backend.app.schemas.directing import DirectingGuidance
from backend.app.schemas.reference import RankedReference


# Accept only persisted search identifiers when saving a reference.
class SaveReferenceRequest(BaseModel):
    """Identify one real ranked reference already owned by a project scene."""

    scene_id: str = Field(min_length=1, max_length=128)
    search_id: str = Field(min_length=1, max_length=128)
    reference_id: str = Field(min_length=1, max_length=256)


# Represent one deduplicated reference in the project Library.
class SavedReference(BaseModel):
    """Durable source-attributed reference derived only from persisted ranking."""

    id: str
    project_id: str
    scene_id: str
    scene_heading: str
    scene_excerpt: str
    reference_id: str
    reference_title: str
    reference_url: HttpUrl
    source_domain: str
    provider: str
    description: str
    overall_score: int = Field(ge=0, le=100)
    score_breakdown: dict[str, int]
    match_reason: str
    reference_type: str
    image_url: HttpUrl | None = None
    tags: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


# Accept only a server-persisted guidance draft when creating a board.
class SaveDirectingBoardRequest(BaseModel):
    """Create a board from one verified guidance draft."""

    scene_id: str = Field(min_length=1, max_length=128)
    guidance_id: str = Field(min_length=1, max_length=128)
    user_title: str = Field(default="", max_length=160)
    notes: str = Field(default="", max_length=4000)


# Persist a directing board with its selected source and validated recommendations.
class SavedDirectingBoard(BaseModel):
    """Durable directing workspace stored beneath its owning project."""

    id: str
    project_id: str
    scene_id: str
    scene_heading: str
    selected_reference: RankedReference
    directing_guidance: DirectingGuidance
    user_title: str
    notes: str
    created_at: datetime
    updated_at: datetime


# Preserve generation drafts server-side so boards cannot accept browser-authored guidance.
class DirectingGuidanceDraft(BaseModel):
    """Server-owned generated guidance and its immutable ranked source."""

    id: str
    project_id: str
    search_id: str
    scene_id: str
    selected_reference: RankedReference
    directing_guidance: DirectingGuidance
    created_at: datetime
    updated_at: datetime

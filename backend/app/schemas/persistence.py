"""Typed contracts for durable project workflow persistence."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from backend.app.schemas.reference import RankedReference, ReferenceSearchPreferences
from backend.app.schemas.scene import AnalyzedScene, SceneAnalysis
from backend.app.schemas.search_plan import SearchPlan


class ProjectRecord(BaseModel):
    """Durable project metadata and the latest screenplay analysis."""

    project_id: str
    title: str
    filename: str
    created_at: datetime
    updated_at: datetime
    status: str = "analyzed"
    screenplay_metadata: dict[str, Any] = Field(default_factory=dict)
    selected_scene_id: str | None = None
    latest_search_preferences: ReferenceSearchPreferences | None = None
    scene_count: int = 0
    selected_reference_count: int = 0


class ProjectDetail(ProjectRecord):
    """Project metadata with persisted scenes for the detail workflow."""

    scenes: list[AnalyzedScene] = Field(default_factory=list)


class SearchRecord(BaseModel):
    """One immutable reference-search execution."""

    search_id: str
    project_id: str
    scene_id: str
    queries: list[str] = Field(default_factory=list)
    preferences: ReferenceSearchPreferences
    created_at: datetime
    raw_candidate_count: int = 0
    retained_candidate_count: int = 0
    retry_count: int = 0
    status: str
    failed_queries: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    search_plan: SearchPlan | None = None


class SearchDetail(SearchRecord):
    """Search execution with its ranked, source-linked results."""

    references: list[RankedReference] = Field(default_factory=list)
    chosen_reference_id: str | None = None


class RefinementRecord(BaseModel):
    """One user refinement and the searches it connects."""

    refinement_id: str
    project_id: str
    scene_id: str
    user_text: str
    parsed_preferences: ReferenceSearchPreferences
    previous_search_id: str | None = None
    resulting_search_id: str | None = None
    created_at: datetime


class SelectionUpdate(BaseModel):
    """Request to select or clear a reference for a scene."""

    search_id: str | None = None
    reference_id: str | None = None


class RefinementRequest(BaseModel):
    """Request to record a refinement before a subsequent search."""

    user_text: str = Field(min_length=1, max_length=500)
    parsed_preferences: ReferenceSearchPreferences
    previous_search_id: str | None = None


class AnalysisPersistencePayload(BaseModel):
    """Structured result written after screenplay analysis completes."""

    project_id: str
    filename: str
    character_count: int
    scenes: list[AnalyzedScene]
    screenplay_metadata: dict[str, Any] = Field(default_factory=dict)


class SceneUpdatePayload(BaseModel):
    """Optional scene-analysis replacement payload for future re-analysis."""

    scene_analysis: SceneAnalysis


class ProjectCreateRequest(BaseModel):
    """Create a lightweight project before screenplay analysis begins."""

    project_id: str
    title: str
    filename: str


class ProjectUpdateRequest(BaseModel):
    """Edit user-facing project metadata without replacing scene data."""

    title: str | None = None
    selected_scene_id: str | None = None

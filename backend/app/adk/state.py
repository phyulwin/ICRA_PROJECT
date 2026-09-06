# backend/app/adk/state.py
"""Typed, JSON-serializable state for local ADK and Agent Engine sessions."""

from typing import Any

from pydantic import BaseModel, Field

from backend.app.schemas.reference import (
    CulturalReferenceCandidate,
    RankedReference,
    ReferenceSearchPreferences,
)
from backend.app.schemas.scene import Scene, SceneAnalysis


# Record one retrieval round without retaining uploaded media or credentials.
class SearchHistoryEntry(BaseModel):
    """Trace one bounded Parallel retrieval round."""

    queries: list[str] = Field(default_factory=list)
    candidate_count: int = Field(default=0, ge=0)
    status: str


# Keep the latest tool outcome explicit for resumable browser and remote sessions.
class ToolStatus(BaseModel):
    """Describe the last completed ADK tool operation."""

    tool_name: str
    status: str
    message: str = ""


# Define all durable workflow state as Pydantic-validated JSON data.
class ProjectSessionState(BaseModel):
    """State shared by the Cultural Reference Director root agent."""

    project_id: str = ""
    screenplay_metadata: dict[str, Any] = Field(default_factory=dict)
    selected_scene_id: str | None = None
    scene: Scene | None = None
    scene_analysis: SceneAnalysis | None = None
    search_preferences: ReferenceSearchPreferences = Field(
        default_factory=ReferenceSearchPreferences
    )
    search_queries: list[str] = Field(default_factory=list)
    search_history: list[SearchHistoryEntry] = Field(default_factory=list)
    raw_reference_candidates: list[CulturalReferenceCandidate] = Field(
        default_factory=list
    )
    ranked_references: list[RankedReference] = Field(default_factory=list)
    selected_reference: RankedReference | None = None
    directing_notes: list[str] = Field(default_factory=list)
    retry_count: int = Field(default=0, ge=0, le=1)
    last_tool_status: ToolStatus | None = None


# Restore validated state from ADK's mutable dictionary representation.
def load_project_state(values: Any) -> ProjectSessionState:
    """Validate a mapping-like ADK session state."""

    try:
        if hasattr(values, "to_dict"):
            payload = values.to_dict()
        else:
            payload = dict(values or {})
        durable_payload = {
            key: value
            for key, value in payload.items()
            if not str(key).startswith("temp:")
        }
        return ProjectSessionState.model_validate(durable_payload)
    except (TypeError, ValueError):
        return ProjectSessionState()


# Persist only JSON-compatible values so local and managed sessions behave alike.
def save_project_state(state: ProjectSessionState, target: Any) -> None:
    """Write validated state back to an ADK session mapping."""

    payload = state.model_dump(mode="json")
    for key, value in payload.items():
        target[key] = value

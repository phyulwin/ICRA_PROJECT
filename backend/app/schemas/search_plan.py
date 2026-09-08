# backend/app/schemas/search_plan.py
"""Structured creative-search planning contracts for retrieval v2."""

from pydantic import BaseModel, Field, model_validator


# Define the stable planner output shared by retrieval, ranking, persistence, and UI.
class SearchPlan(BaseModel):
    """A diverse, preference-aware search strategy generated before Parallel."""

    creative_target: str
    comedic_or_dramatic_mechanism: str
    desired_visual_action: str
    desired_performance: str
    desired_emotional_beat: str
    desired_reference_types: list[str] = Field(default_factory=list)
    platform_targets: list[str] = Field(default_factory=list)
    era_intent: str
    ranking_priority: str
    queries: list[str]
    negative_intents: list[str] = Field(default_factory=list)
    reformulation_diagnosis: str | None = None

    # Require material query diversity at the validated application boundary.
    @model_validator(mode="after")
    def validate_query_strategy(self) -> "SearchPlan":
        """Reject shallow plans and duplicate query sets."""

        normalized = {" ".join(query.casefold().split()) for query in self.queries if query.strip()}
        if not 6 <= len(normalized) <= 12:
            raise ValueError("SearchPlan requires 6 to 12 diverse queries")
        if not self.negative_intents:
            raise ValueError("SearchPlan requires negative search intent")
        return self


# Keep the Vertex serving schema compact and validate limits after generation.
class GeminiSearchPlan(BaseModel):
    """Compact Gemini wire model mapped into SearchPlan."""

    c: str
    m: str
    v: str
    p: str
    e: str
    r: list[str]
    t: list[str]
    a: str
    k: str
    q: list[str]
    n: list[str]
    d: str | None = None

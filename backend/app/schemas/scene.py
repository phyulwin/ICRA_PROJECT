# backend/app/schemas/scene.py
"""Validated data contracts for screenplay and multimodal analysis."""

from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


# Keep public labels stable so the frontend can render them directly.
class ReferenceOpportunity(StrEnum):
    """Business-friendly reference-opportunity classifications."""

    NONE = "no reference needed"
    POSSIBLE = "possible reference opportunity"
    STRONG = "strong reference opportunity"


# Represent one screenplay scene after deterministic document parsing.
class Scene(BaseModel):
    """A screenplay scene with preserved source text and inferred metadata."""

    scene_id: str = Field(description="Stable one-based identifier such as scene_001")
    heading: str = Field(description="Original scene heading")
    location: str = Field(description="Location portion of the scene heading")
    time_of_day: str | None = Field(
        default=None, description="Time portion of the scene heading when present"
    )
    characters: list[str] = Field(default_factory=list)
    raw_text: str = Field(description="Complete scene text, including its heading")


# Capture a character's objective without relying on uncontrolled prose.
class CharacterIntention(BaseModel):
    """The goal or intention attributed to a named scene character."""

    character: str
    intention: str


# Define the complete structured contract returned by the Script Intelligence Agent.
class SceneAnalysis(BaseModel):
    """Gemini's validated creative and cultural analysis for one scene."""

    scene_type: str
    tone: list[str] = Field(min_length=1, max_length=6)
    characters: list[str]
    character_intentions: list[CharacterIntention]
    primary_beat: str
    emotions: list[str]
    comedic_or_dramatic_mechanism: str
    important_actions: list[str]
    visual_characteristics: list[str]
    cultural_concepts: list[str]
    reference_opportunity: ReferenceOpportunity
    reference_opportunity_score: int = Field(ge=0, le=100)
    reference_opportunity_reason: str
    reference_queries: list[str] = Field(max_length=6)

    # Enforce the scoring rubric and Phase 3 query handoff requirements.
    @model_validator(mode="after")
    def validate_reference_opportunity(self) -> "SceneAnalysis":
        """Ensure the label, score, and query count agree with the shared rubric."""

        score_ranges = {
            ReferenceOpportunity.NONE: range(0, 30),
            ReferenceOpportunity.POSSIBLE: range(30, 70),
            ReferenceOpportunity.STRONG: range(70, 101),
        }
        if self.reference_opportunity_score not in score_ranges[
            self.reference_opportunity
        ]:
            raise ValueError("reference opportunity label does not match score")

        if self.reference_opportunity == ReferenceOpportunity.NONE:
            self.reference_queries = []
        elif len(self.reference_queries) < 3:
            raise ValueError("reference opportunities require 3 to 6 search queries")
        return self


# Combine deterministic parsing with Gemini intelligence for API responses.
class AnalyzedScene(BaseModel):
    """A parsed scene paired with its structured Gemini analysis."""

    scene: Scene
    analysis: SceneAnalysis


# Return document-level parsing metadata alongside all extracted scenes.
class DocumentProcessingResult(BaseModel):
    """The structured result of screenplay ingestion and scene extraction."""

    filename: str
    media_type: str
    character_count: int
    scenes: list[Scene]


# Constrain native Gemini document extraction to one screenplay-preserving field.
class ExtractedDocumentText(BaseModel):
    """Text recovered from a PDF that has no locally extractable text layer."""

    text: str = Field(
        min_length=1,
        description=(
            "Complete screenplay text with scene headings, dialogue, and line breaks "
            "preserved in reading order"
        ),
    )


# Return the complete Phase 2 screenplay analysis payload.
class ScreenplayAnalysisResult(BaseModel):
    """All analyzed scenes from an uploaded screenplay."""

    project_id: str | None = None
    filename: str
    media_type: str
    character_count: int
    scenes: list[AnalyzedScene]


# Validate pasted screenplay content sent through the JSON endpoint.
class PastedScreenplayRequest(BaseModel):
    """Request body for processing screenplay text pasted into the application."""

    text: str = Field(min_length=1)
    filename: str = "pasted-screenplay.fountain"


# Capture filmmaking characteristics observed in an image or video.
class MultimodalAnalysis(BaseModel):
    """Structured visual-reference analysis grounded in a screenplay scene."""

    body_language: list[str]
    facial_reaction: list[str]
    movement: list[str]
    framing: list[str]
    camera_movement: list[str]
    visual_composition: list[str]
    pacing_timing: list[str]
    emotional_progression: list[str]
    scene_alignment: str
    directing_takeaways: list[str]


# Carry a scene and uploaded-media analysis together in API responses.
class MultimodalAnalysisResult(BaseModel):
    """Multimodal analysis response tied to its source scene."""

    scene_id: str
    media_type: str
    analysis: MultimodalAnalysis

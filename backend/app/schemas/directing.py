# backend/app/schemas/directing.py
"""Validated contracts for original, reference-grounded directing guidance."""

from pydantic import BaseModel, Field, model_validator


# Define the complete structured Gemini output used by ADK, FastAPI, and the UI.
class DirectingGuidance(BaseModel):
    """Actionable filmmaking guidance abstracted from one verified reference."""

    reference_id: str
    reference_title: str
    scene_id: str
    creative_intent: str
    performance: list[str] = Field(default_factory=list)
    facial_expression: list[str] = Field(default_factory=list)
    body_language: list[str] = Field(default_factory=list)
    blocking: list[str] = Field(default_factory=list)
    camera: list[str] = Field(default_factory=list)
    framing: list[str] = Field(default_factory=list)
    shot_sequence: list[str] = Field(default_factory=list)
    timing: list[str] = Field(default_factory=list)
    editing: list[str] = Field(default_factory=list)
    sound: list[str] = Field(default_factory=list)
    visual_style: list[str] = Field(default_factory=list)
    what_to_borrow: list[str] = Field(default_factory=list)
    what_not_to_copy: list[str] = Field(default_factory=list)
    concise_director_note: str

    # Reject model output that explicitly instructs literal duplication.
    @model_validator(mode="after")
    def validate_transformative_guidance(self) -> "DirectingGuidance":
        """Require useful core sections and prohibit direct-copy instructions."""

        if not self.performance or not self.blocking or not self.timing:
            raise ValueError("performance, blocking, and timing guidance are required")
        if not (self.camera or self.framing or self.shot_sequence):
            raise ValueError("camera or framing guidance is required")
        combined = " ".join(
            [
                self.creative_intent,
                *self.performance,
                *self.blocking,
                *self.camera,
                *self.framing,
                *self.shot_sequence,
                *self.what_to_borrow,
                *self.what_not_to_copy,
                self.concise_director_note,
            ]
        ).casefold()
        prohibited = (
            "copy this shot exactly",
            "recreate the exact",
            "use the exact dialogue",
            "duplicate shot-for-shot",
        )
        if any(phrase in combined for phrase in prohibited):
            raise ValueError("guidance must transform rather than copy the reference")
        return self


# Keep Vertex AI's serving schema compact, then map it into the stable public model.
class GeminiDirectingGuidance(BaseModel):
    """Compact structured wire contract that avoids schema-state explosion."""

    r: str
    t: str
    s: str
    i: str
    p: list[str]
    f: list[str]
    b: list[str]
    k: list[str]
    c: list[str]
    g: list[str]
    q: list[str]
    m: list[str]
    e: list[str]
    u: list[str]
    v: list[str]
    w: list[str]
    x: list[str]
    n: str


# Accept only identifiers that resolve to persisted project-owned source data.
class DirectingGuidanceRequest(BaseModel):
    """Request guidance for one reference in one persisted search."""

    search_id: str = Field(min_length=1, max_length=128)
    reference_id: str = Field(min_length=1, max_length=256)


# Return the persisted draft identifier and immutable source alongside guidance.
class DirectingGuidanceResult(BaseModel):
    """One generated guidance draft ready for rendering or board storage."""

    guidance_id: str
    project_id: str
    search_id: str
    scene_id: str
    reference_url: str
    source_domain: str
    guidance: DirectingGuidance

# backend/app/schemas/reference.py
"""Validated contracts for Parallel discovery and Gemini reference ranking."""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, HttpUrl, model_validator

from backend.app.schemas.scene import Scene, SceneAnalysis
from backend.app.schemas.search_plan import SearchPlan


# Keep reference-type filters stable across the API and frontend.
class ReferenceType(StrEnum):
    """Supported cultural-reference categories."""

    ALL = "all"
    TIKTOK_SHORT_FORM = "tiktok_short_form"
    INSTAGRAM_REELS = "instagram_reels"
    MEMES = "memes"
    REACTION_GIFS = "reaction_gifs"
    FILM = "film"
    TV = "tv"
    ANIME = "anime"
    INTERNET_CULTURE = "internet_culture"
    UNCLASSIFIED = "unclassified"
    TIKTOK = "tiktok_short_form"
    INTERNET = "internet_culture"


# Classify the retrieved page itself rather than echoing the requested filter.
class CulturalReferenceType(StrEnum):
    """Artifact categories used by quality gates and platform badges."""

    REACTION_MEME = "reaction_meme"
    VIRAL_VIDEO = "viral_video"
    TIKTOK = "tiktok"
    INSTAGRAM_REEL = "instagram_reel"
    GIF = "gif"
    FILM_TV_MOMENT = "film_tv_moment"
    ANIME_MOMENT = "anime_moment"
    INFORMATIONAL_ARTICLE = "informational_article"
    OTHER = "other"


# Keep source labels stable across backend normalization and frontend display.
class SourcePlatform(StrEnum):
    """Recognized source platforms for visual cultural artifacts."""

    TIKTOK = "tiktok"
    INSTAGRAM = "instagram"
    YOUTUBE = "youtube"
    GIPHY = "giphy"
    TENOR = "tenor"
    MEME = "meme"
    REDDIT = "reddit"
    FILM_TV = "film_tv"
    WEB = "web"


# Keep era filters explicit and human-readable.
class ReferenceEra(StrEnum):
    """Supported cultural-reference eras."""

    ANY = "any"
    TRENDING_CURRENT = "trending_current"
    TWENTY_TWENTY_PRESENT = "2020_present"
    TWENTY_FIFTEEN_NINETEEN = "2015_2019"
    TWENTY_TEN_FOURTEEN = "2010_2014"
    TWO_THOUSANDS = "2000s"
    PRE_TWO_THOUSAND = "pre_2000"
    CURRENT = "trending_current"
    TWENTY_TWENTIES = "2020_present"
    TWENTY_TENS = "2010_2014"


# Represent the creative dimension that should dominate deterministic ranking.
class MatchFor(StrEnum):
    """Supported reference-matching priorities."""

    BEST_OVERALL = "best_overall"
    PERFORMANCE = "performance"
    FACIAL_EXPRESSION = "facial_expression"
    SITUATION = "situation"
    VISUAL_COMPOSITION = "visual_composition"
    BODY_LANGUAGE = "body_language"
    COMEDIC_TIMING = "comedic_timing"
    EMOTIONAL_BEAT = "emotional_beat"
    CAMERA_FRAMING = "camera_framing"
    ALL = "best_overall"
    ACTING = "performance"
    VISUAL = "visual_composition"
    TIMING = "comedic_timing"


# Validate user-facing search controls before they affect external requests.
class ReferenceSearchPreferences(BaseModel):
    """Filters and limits used for discovery and ranking."""

    reference_type: ReferenceType = ReferenceType.ALL
    era: ReferenceEra = ReferenceEra.ANY
    match_for: MatchFor = MatchFor.BEST_OVERALL
    recognition: int = Field(default=50, ge=0, le=100)
    max_results: int = Field(default=5, ge=3, le=5)

    # Accept persisted v1 filters while normalizing every new request to v2 semantics.
    @model_validator(mode="before")
    @classmethod
    def migrate_v1_preferences(cls, value: object) -> object:
        """Map legacy enum values and obscurity into their v2 equivalents."""

        if not isinstance(value, dict):
            return value
        payload = dict(value)
        type_map = {"tiktok": "tiktok_short_form", "internet": "internet_culture"}
        era_map = {"current": "trending_current", "2020s": "2020_present", "2010s": "2010_2014"}
        match_map = {"all": "best_overall", "acting": "performance", "visual": "visual_composition", "timing": "comedic_timing"}
        payload["reference_type"] = type_map.get(payload.get("reference_type"), payload.get("reference_type", "all"))
        payload["era"] = era_map.get(payload.get("era"), payload.get("era", "any"))
        payload["match_for"] = match_map.get(payload.get("match_for"), payload.get("match_for", "best_overall"))
        if "recognition" not in payload and "obscurity" in payload:
            payload["recognition"] = 100 - int(payload["obscurity"])
        payload.pop("obscurity", None)
        return payload

    # Retain a read-only compatibility view for established provider adapters.
    @property
    def obscurity(self) -> int:
        """Return the inverse v1 value while downstream code migrates to recognition."""

        return 100 - self.recognition


# Preserve one factual result exactly as normalized from Parallel Search.
class CulturalReferenceCandidate(BaseModel):
    """A traceable web candidate returned by Parallel Search."""

    id: str
    title: str
    url: HttpUrl
    source_domain: str
    snippet: str
    image_url: HttpUrl | None = None
    reference_type: ReferenceType
    cultural_reference_type: CulturalReferenceType = CulturalReferenceType.OTHER
    source_platform: SourcePlatform = SourcePlatform.WEB
    discovered_from_query: str
    discovered_from_queries: list[str] = Field(default_factory=list)
    search_family: str = "general"
    published_at: str | None = None
    source_metadata: dict[str, Any] = Field(default_factory=dict)


# Record a failed query without discarding successful Parallel results.
class SearchQueryFailure(BaseModel):
    """Non-fatal failure associated with one attempted web query."""

    query: str
    error_type: str
    message: str


# Carry normalized discovery output independently from Gemini assessment.
class CulturalSearchResult(BaseModel):
    """Raw Parallel candidates and operational search traceability."""

    candidates: list[CulturalReferenceCandidate]
    searched_queries: list[str]
    failed_queries: list[SearchQueryFailure] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    session_ids: list[str] = Field(default_factory=list)
    raw_candidate_count: int = Field(default=0, ge=0)
    rejected_candidate_count: int = Field(default=0, ge=0)
    extracted_candidate_count: int = Field(default=0, ge=0)
    retry_count: int = Field(default=0, ge=0, le=1)
    search_plan: SearchPlan | None = None

    # Make partial success explicit for HTTP consumers.
    @property
    def partial_success(self) -> bool:
        """Return whether at least one query failed while the batch continued."""

        return bool(self.failed_queries)


# Constrain Gemini to component judgments and prevent model-owned final scores.
class ReferenceAssessment(BaseModel):
    """Gemini relevance assessment for one real Parallel candidate."""

    candidate_id: str
    emotional_similarity: int = Field(ge=0, le=100)
    situational_similarity: int = Field(ge=0, le=100)
    facial_expression_similarity: int = Field(default=0, ge=0, le=100)
    performance_similarity: int = Field(default=0, ge=0, le=100)
    body_language_similarity: int = Field(default=0, ge=0, le=100)
    visual_similarity: int = Field(ge=0, le=100)
    acting_similarity: int = Field(ge=0, le=100)
    timing_similarity: int = Field(ge=0, le=100)
    camera_framing_similarity: int = Field(default=0, ge=0, le=100)
    recognizability: int = Field(ge=0, le=100)
    cultural_relevance: int = Field(ge=0, le=100)
    artifact_verified: bool
    cultural_reference_type: CulturalReferenceType
    artifact_quality: int = Field(ge=0, le=100)
    artifact_evidence: str
    match_reason: str
    tags: list[str] = Field(default_factory=list, max_length=6)
    useful_directing_elements: list[str] = Field(default_factory=list, max_length=6)
    best_for: list[str] = Field(default_factory=list, max_length=3)
    recognizability_is_inferred: bool = True


# Give Gemini one schema for assessing a bounded candidate collection.
class ReferenceAssessmentBatch(BaseModel):
    """Structured Gemini assessments keyed only by real candidate IDs."""

    assessments: list[ReferenceAssessment] = Field(min_length=1, max_length=12)


# Keep the Gemini-facing schema small enough for Vertex AI structured serving.
class GeminiReferenceAssessment(BaseModel):
    """Compact wire response that is validated into ReferenceAssessment."""

    id: str
    emotion: int
    situation: int
    facial: int
    performance: int
    body: int
    visual: int
    acting: int
    timing: int
    camera: int
    recognition: int
    culture: int
    artifact: bool
    kind: str
    quality: int
    evidence: str
    reason: str
    tags: list[str] = Field(default_factory=list)
    elements: list[str] = Field(default_factory=list)


# Avoid nested bounds in the serving schema while retaining JSON structure.
class GeminiReferenceAssessmentBatch(BaseModel):
    """Serving-compatible Gemini response containing compact assessments."""

    items: list[GeminiReferenceAssessment]


# Combine raw source facts with separate assessment and deterministic scoring.
class RankedReference(BaseModel):
    """A ranked, traceable cultural reference ready for presentation."""

    reference: CulturalReferenceCandidate
    assessment: ReferenceAssessment
    overall_score: int = Field(ge=0, le=100)


# Submit existing Phase 2 state without rerunning screenplay analysis.
class ReferenceSearchRequest(BaseModel):
    """Existing scene intelligence plus user discovery preferences."""

    project_id: str | None = None
    scene: Scene
    scene_analysis: SceneAnalysis
    preferences: ReferenceSearchPreferences = Field(
        default_factory=ReferenceSearchPreferences
    )

    # Prevent a client from pairing analysis with a different scene identifier.
    @model_validator(mode="after")
    def validate_scene_identity(self) -> "ReferenceSearchRequest":
        """Retain one authoritative scene identity throughout the pipeline."""

        if not self.scene.scene_id:
            raise ValueError("scene_id is required")
        return self


# Return ranked references alongside provider-level execution details.
class ReferenceSearchResponse(BaseModel):
    """Complete Phase 3 discovery and ranking response."""

    scene_id: str
    references: list[RankedReference]
    raw_candidate_count: int = Field(ge=0)
    rejected_candidate_count: int = Field(default=0, ge=0)
    extracted_candidate_count: int = Field(default=0, ge=0)
    searched_queries: list[str]
    failed_queries: list[SearchQueryFailure] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    partial_success: bool = False
    retry_count: int = Field(default=0, ge=0, le=1)
    search_id: str | None = None
    search_plan: SearchPlan | None = None


# Limit the optional Gemini reformulation pass to concise search intent.
class QueryReformulation(BaseModel):
    """One bounded replacement set for weak Parallel search results."""

    queries: list[str] = Field(min_length=1, max_length=3)

# backend/tests/test_reference_ranker.py
"""Tests for structured Gemini assessment and deterministic score calculation."""

from types import SimpleNamespace

import pytest

from backend.app.agents.reference_ranker import (
    ReferenceRanker,
    ReferenceRankingError,
    calculate_weighted_score,
)
from backend.app.schemas.reference import (
    CulturalReferenceCandidate,
    CulturalReferenceType,
    GeminiReferenceAssessmentBatch,
    MatchFor,
    ReferenceAssessment,
    ReferenceSearchPreferences,
    ReferenceType,
    SourcePlatform,
)
from backend.app.schemas.scene import Scene, SceneAnalysis


# Simulate Gemini's models surface and preserve the outbound structured request.
class FakeRankingModels:
    """Return configured component assessments without an overall score."""

    def __init__(self, assessments: list[dict[str, object]]) -> None:
        """Store assessment output and request capture state."""

        self.assessments = assessments
        self.last_request: dict[str, object] = {}

    def generate_content(self, **kwargs: object) -> SimpleNamespace:
        """Capture the request and return schema-compatible assessment data."""

        self.last_request = kwargs
        return SimpleNamespace(
            parsed={"items": self.assessments},
            text="",
        )


# Match the production Gemini client's models attribute.
class FakeRankingClient:
    """Minimal injected Gemini ranking client."""

    def __init__(self, assessments: list[dict[str, object]]) -> None:
        """Expose fake model generation methods."""

        self.models = FakeRankingModels(assessments)


# Build one valid scene and existing Phase 2 analysis for ranking tests.
def build_scene_context() -> tuple[Scene, SceneAnalysis]:
    """Return a scene and its already-completed structured analysis."""

    scene = Scene(
        scene_id="scene_001",
        heading="INT. APARTMENT - NIGHT",
        location="APARTMENT",
        time_of_day="NIGHT",
        characters=["JOHN"],
        raw_text="INT. APARTMENT - NIGHT\nJOHN slowly stops smiling.",
    )
    analysis = SceneAnalysis(
        scene_type="comedy",
        tone=["awkward"],
        characters=["JOHN"],
        character_intentions=[
            {"character": "JOHN", "intention": "hide the obvious lie"}
        ],
        primary_beat="John realizes everyone sees the evidence",
        emotions=["confidence", "embarrassment"],
        comedic_or_dramatic_mechanism="delayed realization",
        important_actions=["John stops smiling"],
        visual_characteristics=["frosting on shirt"],
        cultural_concepts=["caught in a lie"],
        reference_opportunity="strong reference opportunity",
        reference_opportunity_score=90,
        reference_opportunity_reason="A reaction reference can guide performance.",
        reference_queries=[
            "caught lying reaction meme",
            "awkward realization comedy scene",
            "guilty facial reaction timing",
        ],
    )
    return scene, analysis


# Build one traceable Parallel candidate without assessment fields mixed into it.
def build_candidate(candidate_id: str = "ref_real") -> CulturalReferenceCandidate:
    """Return a normalized raw reference candidate."""

    return CulturalReferenceCandidate(
        id=candidate_id,
        title="Real reaction scene",
        url="https://example.com/real-reference",
        source_domain="example.com",
        snippet="A character's confident expression collapses after being caught.",
        reference_type=ReferenceType.FILM,
        cultural_reference_type=CulturalReferenceType.FILM_TV_MOMENT,
        source_platform=SourcePlatform.FILM_TV,
        discovered_from_query="caught lying reaction meme",
        published_at=None,
        source_metadata={"provider": "parallel"},
    )


# Confirm the documented base weights are calculated by application code.
def test_weighted_score_calculation() -> None:
    """Calculate the final score without accepting a model percentage."""

    assessment = ReferenceAssessment(
        candidate_id="ref_real",
        emotional_similarity=80,
        situational_similarity=90,
        visual_similarity=70,
        acting_similarity=80,
        timing_similarity=60,
        recognizability=60,
        cultural_relevance=50,
        artifact_verified=True,
        cultural_reference_type=CulturalReferenceType.FILM_TV_MOMENT,
        artifact_quality=85,
        artifact_evidence="A direct scene page identifies the visible reaction.",
        match_reason="The delayed reaction mirrors the screenplay beat.",
        tags=["reaction"],
    )

    score = calculate_weighted_score(
        assessment,
        ReferenceSearchPreferences(obscurity=50),
    )

    assert score == 74


# Confirm Match For changes deterministic weights rather than model-owned sorting.
def test_match_priority_changes_weighted_score() -> None:
    """Give visual similarity greater influence for a visual search."""

    assessment = ReferenceAssessment(
        candidate_id="ref_real",
        emotional_similarity=20,
        situational_similarity=20,
        visual_similarity=100,
        acting_similarity=20,
        timing_similarity=20,
        recognizability=60,
        cultural_relevance=20,
        artifact_verified=True,
        cultural_reference_type=CulturalReferenceType.FILM_TV_MOMENT,
        artifact_quality=80,
        artifact_evidence="A direct scene page shows the composition.",
        match_reason="The composition is the primary similarity.",
        tags=["visual"],
    )

    baseline = calculate_weighted_score(
        assessment,
        ReferenceSearchPreferences(match_for=MatchFor.ALL),
    )
    visual = calculate_weighted_score(
        assessment,
        ReferenceSearchPreferences(match_for=MatchFor.VISUAL),
    )

    assert visual > baseline


# Confirm Gemini cannot alter source facts and final scores are locally attached.
def test_ranker_preserves_parallel_source_and_sorts() -> None:
    """Join structured assessments to immutable candidate URLs and titles."""

    assessment = {
        "id": "ref_real",
        "emotion": 80,
        "situation": 90,
        "visual": 70,
        "acting": 80,
        "timing": 60,
        "recognition": 60,
        "culture": 50,
        "artifact": True,
        "kind": "film_tv_moment",
        "quality": 85,
        "evidence": "A direct scene page identifies the visible reaction.",
        "reason": "The delayed reaction mirrors the screenplay beat.",
        "tags": ["reaction", "awkward"],
    }
    client = FakeRankingClient([assessment])
    ranker = ReferenceRanker(client=client, model_name="test-model")
    scene, scene_analysis = build_scene_context()

    ranked = ranker.rank(
        scene,
        scene_analysis,
        [build_candidate()],
        ReferenceSearchPreferences(),
    )

    assert ranked[0].overall_score == 74
    assert ranked[0].reference.title == "Real reaction scene"
    assert str(ranked[0].reference.url) == "https://example.com/real-reference"
    assert client.models.last_request["model"] == "test-model"
    config = client.models.last_request["config"]
    assert config.response_schema is GeminiReferenceAssessmentBatch
    assert len(config.safety_settings) == 4


# Ensure serving constraints remain separate from strict application validation.
def test_ranker_rejects_out_of_range_wire_score() -> None:
    """Reject a Gemini score outside 0–100 after structured generation."""

    invalid_assessment = {
        "id": "ref_real",
        "emotion": 101,
        "situation": 90,
        "visual": 70,
        "acting": 80,
        "timing": 60,
        "recognition": 60,
        "culture": 50,
        "artifact": True,
        "kind": "film_tv_moment",
        "quality": 85,
        "evidence": "A direct scene page identifies the visible reaction.",
        "reason": "Invalid score should not enter deterministic ranking.",
        "tags": ["reaction"],
    }
    client = FakeRankingClient([invalid_assessment])
    ranker = ReferenceRanker(client=client, model_name="test-model")
    scene, scene_analysis = build_scene_context()

    with pytest.raises(ReferenceRankingError):
        ranker.rank(
            scene,
            scene_analysis,
            [build_candidate()],
            ReferenceSearchPreferences(),
        )


# Guard against reintroducing expensive numeric bounds into Vertex serving.
def test_gemini_wire_schema_has_no_numeric_state_bounds() -> None:
    """Keep score bounds in domain validation rather than response_schema."""

    schema = GeminiReferenceAssessmentBatch.model_json_schema()
    assessment_schema = schema["$defs"]["GeminiReferenceAssessment"]
    emotion_schema = assessment_schema["properties"]["emotion"]

    assert "minimum" not in emotion_schema
    assert "maximum" not in emotion_schema
    assert "maxItems" not in schema["properties"]["items"]


# Keep informational webpages out of ranked references even with high similarity.
def test_ranker_quality_gate_rejects_article() -> None:
    """Return no top result when Gemini verifies the page is only an article."""

    article_assessment = {
        "id": "ref_real",
        "emotion": 95,
        "situation": 95,
        "visual": 95,
        "acting": 95,
        "timing": 95,
        "recognition": 95,
        "culture": 95,
        "artifact": False,
        "kind": "informational_article",
        "quality": 10,
        "evidence": "The URL is an advice article without an identifiable clip.",
        "reason": "The topic is similar but no performance can be observed.",
        "tags": ["article"],
    }
    client = FakeRankingClient([article_assessment])
    ranker = ReferenceRanker(client=client, model_name="test-model")
    scene, scene_analysis = build_scene_context()

    article_candidate = build_candidate().model_copy(
        update={
            "cultural_reference_type": CulturalReferenceType.INFORMATIONAL_ARTICLE,
            "source_platform": SourcePlatform.WEB,
        }
    )
    ranked = ranker.rank(
        scene,
        scene_analysis,
        [article_candidate],
        ReferenceSearchPreferences(),
    )

    assert ranked == []


# Confirm direct media URL evidence overrides only artifact-existence uncertainty.
def test_ranker_accepts_direct_artifact_despite_model_uncertainty() -> None:
    """Retain a direct GIF while preserving Gemini's performance scores."""

    uncertain_assessment = {
        "id": "ref_real",
        "emotion": 80,
        "situation": 80,
        "visual": 80,
        "acting": 80,
        "timing": 80,
        "recognition": 80,
        "culture": 80,
        "artifact": False,
        "kind": "other",
        "quality": 20,
        "evidence": "",
        "reason": "The frozen reaction matches the scene performance.",
        "tags": ["reaction"],
    }
    client = FakeRankingClient([uncertain_assessment])
    ranker = ReferenceRanker(client=client, model_name="test-model")
    scene, scene_analysis = build_scene_context()

    ranked = ranker.rank(
        scene,
        scene_analysis,
        [build_candidate()],
        ReferenceSearchPreferences(),
    )

    assert ranked[0].assessment.artifact_verified is True
    assert ranked[0].assessment.artifact_quality == 70

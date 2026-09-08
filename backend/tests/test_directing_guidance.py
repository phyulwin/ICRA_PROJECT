# backend/tests/test_directing_guidance.py
"""Tests for compact Gemini directing output and transformative validation."""

from types import SimpleNamespace

import pytest

from backend.app.agents.directing_guidance import DirectingGuidanceAgent, DirectingGuidanceError
from backend.app.adk.state import ProjectSessionState, load_project_state
from backend.app.schemas.directing import GeminiDirectingGuidance
from backend.app.schemas.reference import CulturalReferenceCandidate, RankedReference, ReferenceAssessment
from backend.app.schemas.scene import Scene, SceneAnalysis


# Build one complete scene and its existing Phase 2 intelligence.
def build_scene_context() -> tuple[Scene, SceneAnalysis]:
    """Return stable input grounded in one screenplay beat."""

    scene = Scene(scene_id="scene_001", heading="INT. ROOM - NIGHT", location="ROOM", time_of_day="NIGHT", characters=["ANA"], raw_text="INT. ROOM - NIGHT\nANA freezes.")
    analysis = SceneAnalysis.model_validate({"scene_type": "comedy", "tone": ["awkward"], "characters": ["ANA"], "character_intentions": [{"character": "ANA", "intention": "hide a mistake"}], "primary_beat": "Ana realizes she is caught", "emotions": ["embarrassment"], "comedic_or_dramatic_mechanism": "delayed reaction", "important_actions": ["Ana freezes"], "visual_characteristics": ["held reaction"], "cultural_concepts": ["caught in a lie"], "reference_opportunity": "strong reference opportunity", "reference_opportunity_score": 85, "reference_opportunity_reason": "A reference can guide performance.", "reference_queries": ["awkward realization reaction", "caught lying performance pause", "delayed embarrassment reaction"]})
    return scene, analysis


# Build one server-persisted reference shape with immutable source evidence.
def build_reference() -> RankedReference:
    """Return a validated Parallel candidate and Gemini assessment."""

    candidate = CulturalReferenceCandidate.model_validate({"id": "parallel_001", "title": "Awkward reaction", "url": "https://example.com/reaction", "source_domain": "example.com", "snippet": "A performer pauses before reacting.", "reference_type": "film", "cultural_reference_type": "film_tv_moment", "source_platform": "film_tv", "discovered_from_query": "awkward realization reaction", "source_metadata": {"provider": "parallel"}})
    assessment = ReferenceAssessment.model_validate({"candidate_id": "parallel_001", "emotional_similarity": 90, "situational_similarity": 88, "visual_similarity": 70, "acting_similarity": 92, "timing_similarity": 91, "recognizability": 60, "cultural_relevance": 70, "artifact_verified": True, "cultural_reference_type": "film_tv_moment", "artifact_quality": 80, "artifact_evidence": "The source describes a delayed reaction.", "match_reason": "Both rely on a held realization.", "tags": ["awkward"]})
    return RankedReference(reference=candidate, assessment=assessment, overall_score=85)


# Return the compact serving payload used to avoid Vertex schema-state overflow.
def compact_payload() -> dict[str, object]:
    """Create one valid compact Gemini response."""

    return {"r": "parallel_001", "t": "Awkward reaction", "s": "scene_001", "i": "Build discomfort through restraint.", "p": ["Let the realization arrive gradually."], "f": ["Hold the eyes before breaking contact."], "b": ["Keep the shoulders still."], "k": ["Pause at the table before stepping back."], "c": ["Use a restrained push-in."], "g": ["Favor a medium close-up."], "q": ["Begin wide, then cut closer on recognition."], "m": ["Hold one beat longer than comfortable."], "e": ["Delay the reaction cut."], "u": ["Let room tone carry the pause."], "v": ["Keep the palette natural."], "w": ["Borrow the delayed recognition mechanism."], "x": ["Do not reproduce dialogue or shot order."], "n": "Play the recognition quietly, then let the pause expose it."}


# Verify Gemini receives the compact schema and returns the stable public contract.
def test_directing_agent_maps_compact_structured_output() -> None:
    """Expand validated short keys without free-form JSON or markdown stripping."""

    captured: dict[str, object] = {}

    # Capture Gemini configuration while returning schema-shaped parsed data.
    def generate_content(**kwargs: object) -> SimpleNamespace:
        """Return one deterministic parsed response."""

        captured.update(kwargs)
        return SimpleNamespace(parsed=compact_payload(), text="")

    client = SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
    scene, analysis = build_scene_context()
    result = DirectingGuidanceAgent(client=client).generate(scene, analysis, build_reference())

    assert result.reference_id == "parallel_001"
    assert result.camera == ["Use a restrained push-in."]
    assert captured["config"].response_mime_type == "application/json"
    assert captured["config"].response_schema.__name__ == "GeminiDirectingGuidance"


# Reject an otherwise structured response that changes source ownership.
def test_directing_agent_rejects_reference_identity_change() -> None:
    """Prevent Gemini from substituting an unverified cultural source."""

    payload = compact_payload()
    payload["r"] = "invented_reference"
    client = SimpleNamespace(models=SimpleNamespace(generate_content=lambda **kwargs: SimpleNamespace(parsed=payload, text="")))
    scene, analysis = build_scene_context()
    with pytest.raises(DirectingGuidanceError):
        DirectingGuidanceAgent(client=client).generate(scene, analysis, build_reference())


# Enforce the public schema's explicit anti-copying safeguard.
def test_directing_schema_rejects_literal_copy_instruction() -> None:
    """Disallow exact recreation instructions at the validation boundary."""

    payload = compact_payload()
    payload["p"] = ["Copy this shot exactly."]
    with pytest.raises(ValueError):
        DirectingGuidanceAgent._to_guidance(GeminiDirectingGuidance.model_validate(payload))


# Verify the managed-session round trip retains the full selected reference.
def test_project_session_state_preserves_selected_reference() -> None:
    """Keep source evidence available when ADK reconstructs session state."""

    selected = build_reference()
    state = ProjectSessionState(selected_reference_id=selected.reference.id, selected_reference=selected)
    restored = load_project_state(state.model_dump(mode="json"))

    assert restored.selected_reference is not None
    assert restored.selected_reference.reference.id == "parallel_001"

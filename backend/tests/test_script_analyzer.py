# backend/tests/test_script_analyzer.py
"""Tests for schema-constrained Script Intelligence Agent output."""

from types import SimpleNamespace

from backend.app.agents.script_analyzer import ScriptIntelligenceAgent
from backend.app.schemas.scene import ReferenceOpportunity, Scene, SceneAnalysis


# Simulate the SDK model interface while retaining the outbound request for assertions.
class FakeModels:
    """Return a deterministic structured response in place of Gemini."""

    def __init__(self, payload: dict[str, object]) -> None:
        """Store the payload returned to the agent."""

        self.payload = payload
        self.last_request: dict[str, object] = {}

    def generate_content(self, **kwargs: object) -> SimpleNamespace:
        """Capture Gemini arguments and return parsed response data."""

        self.last_request = kwargs
        return SimpleNamespace(parsed=self.payload, text="")


# Wrap fake models with the same attribute shape as google.genai.Client.
class FakeClient:
    """Minimal injected Gemini client used by unit tests."""

    def __init__(self, payload: dict[str, object]) -> None:
        """Expose a fake models service."""

        self.models = FakeModels(payload)


# Verify all Phase 2 fields and the opportunity rubric survive validation.
def test_script_agent_returns_validated_analysis() -> None:
    """Analyze a scene with a fake Gemini client and validate structured output."""

    payload = {
        "scene_type": "comedy",
        "tone": ["awkward", "dry"],
        "characters": ["JOHN"],
        "character_intentions": [
            {"character": "JOHN", "intention": "conceal that he ate the cake"}
        ],
        "primary_beat": "John realizes his lie is visibly exposed",
        "emotions": ["confidence", "alarm", "embarrassment"],
        "comedic_or_dramatic_mechanism": "dramatic irony and delayed reaction",
        "important_actions": ["John stops smiling"],
        "visual_characteristics": ["frosting visible on shirt"],
        "cultural_concepts": ["caught in a lie", "awkward realization"],
        "reference_opportunity": "strong reference opportunity",
        "reference_opportunity_score": 88,
        "reference_opportunity_reason": "A visual reaction reference can guide timing.",
        "reference_queries": [
            "caught lying delayed facial reaction visual comedy",
            "awkward realization everyone staring reaction scene",
            "guilty freeze slow eye movement comedy timing",
        ],
    }
    client = FakeClient(payload)
    agent = ScriptIntelligenceAgent(client=client, model_name="test-model")
    scene = Scene(
        scene_id="scene_001",
        heading="INT. APARTMENT - NIGHT",
        location="APARTMENT",
        time_of_day="NIGHT",
        characters=["JOHN"],
        raw_text="INT. APARTMENT - NIGHT\nJOHN\nI did not eat it.",
    )

    result = agent.analyze_scene(scene)

    assert result.reference_opportunity == ReferenceOpportunity.STRONG
    assert len(result.reference_queries) == 3
    assert client.models.last_request["model"] == "test-model"
    config = client.models.last_request["config"]
    assert config.response_schema is SceneAnalysis
    assert len(config.safety_settings) == 4

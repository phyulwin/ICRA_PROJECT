# backend/tests/test_agent_engine_service.py
"""Contract tests for the Cloud Run to Agent Engine gateway."""

import asyncio

from backend.app.schemas.scene import Scene
from backend.app.services.agent_engine_service import AgentEngineGateway


# Simulate the managed async session protocol without external credentials.
class FakeRemoteAgent:
    """Return one genuine-shaped ADK function-response event."""

    async def async_create_session(self, user_id: str, state: dict) -> dict:
        """Capture validated initial state and return a managed session identifier."""

        assert user_id.startswith("cloud_run_")
        assert state["scene"]["scene_id"] == "scene_001"
        return {"id": "session-1"}

    async def async_stream_query(self, user_id: str, session_id: str, message: str):
        """Yield a structured analyze_scene tool response."""

        yield {
            "content": {
                "parts": [
                    {
                        "functionResponse": {
                            "name": "analyze_scene",
                            "response": {
                                "scene_analysis": {
                                    "scene_type": "comedy",
                                    "tone": ["awkward"],
                                    "characters": ["JOHN"],
                                    "character_intentions": [
                                        {"character": "JOHN", "intention": "hide the lie"}
                                    ],
                                    "primary_beat": "The lie becomes visible.",
                                    "emotions": ["embarrassment"],
                                    "comedic_or_dramatic_mechanism": "dramatic irony",
                                    "important_actions": ["John stops smiling"],
                                    "visual_characteristics": ["frosting reveal"],
                                    "cultural_concepts": ["caught lying"],
                                    "reference_opportunity": "strong reference opportunity",
                                    "reference_opportunity_score": 85,
                                    "reference_opportunity_reason": "A recognizable reaction beat.",
                                    "reference_queries": [
                                        "caught lying reaction meme",
                                        "awkward realization gif",
                                        "slow smile fade reaction",
                                    ],
                                }
                            },
                        }
                    }
                ]
            }
        }


# Ensure managed results pass through the same Pydantic schema as local analysis.
def test_agent_engine_gateway_validates_scene_analysis() -> None:
    """Parse a managed function response into the public SceneAnalysis model."""

    gateway = AgentEngineGateway()
    gateway._remote_agent = FakeRemoteAgent()
    scene = Scene(
        scene_id="scene_001",
        heading="INT. APARTMENT - NIGHT",
        location="APARTMENT",
        time_of_day="NIGHT",
        characters=["JOHN"],
        raw_text="INT. APARTMENT - NIGHT\nJOHN stops smiling.",
    )
    result = asyncio.run(gateway.analyze_scene(scene))
    assert result.reference_opportunity_score == 85
    assert len(result.reference_queries) == 3

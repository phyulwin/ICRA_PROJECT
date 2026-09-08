# backend/tests/test_reference_api.py
"""HTTP contract tests for Phase 3 reference discovery."""

from fastapi.testclient import TestClient

import backend.app.main as main_module
from backend.app.schemas.reference import ReferenceSearchResponse


# Return a deterministic endpoint response without contacting external services.
class FakeReferenceDiscoveryService:
    """Capture the validated request and return an empty real-search outcome."""

    def __init__(self) -> None:
        """Initialize request capture state."""

        self.last_request = None

    def find_references(self, request: object, cancellation_token: object = None) -> ReferenceSearchResponse:
        """Return a schema-valid no-results response for the requested scene."""

        self.last_request = request
        return ReferenceSearchResponse(
            scene_id=request.scene.scene_id,
            references=[],
            raw_candidate_count=0,
            searched_queries=request.scene_analysis.reference_queries,
        )


# Build a complete request from existing scene and analysis state.
def build_request() -> dict[str, object]:
    """Return a valid Phase 3 request body."""

    return {
        "scene": {
            "scene_id": "scene_001",
            "heading": "INT. APARTMENT - NIGHT",
            "location": "APARTMENT",
            "time_of_day": "NIGHT",
            "characters": ["JOHN"],
            "raw_text": "INT. APARTMENT - NIGHT\nJOHN slowly stops smiling.",
        },
        "scene_analysis": {
            "scene_type": "comedy",
            "tone": ["awkward"],
            "characters": ["JOHN"],
            "character_intentions": [
                {"character": "JOHN", "intention": "hide the lie"}
            ],
            "primary_beat": "John realizes everyone sees the evidence",
            "emotions": ["confidence", "embarrassment"],
            "comedic_or_dramatic_mechanism": "delayed realization",
            "important_actions": ["John stops smiling"],
            "visual_characteristics": ["frosting on shirt"],
            "cultural_concepts": ["caught in a lie"],
            "reference_opportunity": "strong reference opportunity",
            "reference_opportunity_score": 90,
            "reference_opportunity_reason": "A reaction reference can guide performance.",
            "reference_queries": [
                "caught lying reaction meme",
                "awkward realization comedy scene",
                "guilty facial reaction timing",
            ],
        },
        "preferences": {
            "reference_type": "memes",
            "era": "2010s",
            "match_for": "acting",
            "obscurity": 35,
            "max_results": 5,
        },
    }


# Confirm the endpoint uses supplied Phase 2 state and does not rerun analysis.
def test_reference_endpoint_accepts_existing_scene_analysis(monkeypatch: object) -> None:
    """Pass validated scene intelligence into the discovery service."""

    fake_service = FakeReferenceDiscoveryService()
    monkeypatch.setattr(
        main_module,
        "reference_discovery_service",
        fake_service,
    )
    client = TestClient(main_module.app)

    response = client.post(
        "/api/v1/scenes/scene_001/references",
        json=build_request(),
    )

    assert response.status_code == 200
    assert response.json()["scene_id"] == "scene_001"
    assert fake_service.last_request.preferences.reference_type == "memes"


# Confirm mismatched route and payload identities are rejected before external calls.
def test_reference_endpoint_rejects_scene_mismatch(monkeypatch: object) -> None:
    """Reject a request that attempts to pair a different scene with the route."""

    fake_service = FakeReferenceDiscoveryService()
    monkeypatch.setattr(
        main_module,
        "reference_discovery_service",
        fake_service,
    )
    client = TestClient(main_module.app)

    response = client.post(
        "/api/v1/scenes/scene_999/references",
        json=build_request(),
    )

    assert response.status_code == 400
    assert fake_service.last_request is None

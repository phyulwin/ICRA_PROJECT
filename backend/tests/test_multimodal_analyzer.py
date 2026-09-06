# backend/tests/test_multimodal_analyzer.py
"""Tests for reusable structured image and video reference analysis."""

from types import SimpleNamespace

from google.genai import types

from backend.app.schemas.scene import Scene
from backend.app.services.multimodal_analyzer import (
    MultimodalAnalysisError,
    MultimodalAnalyzer,
)


# Simulate Gemini's models surface and retain the generated request.
class FakeModels:
    """Return deterministic multimodal characteristics."""

    def __init__(self) -> None:
        """Initialize request capture state."""

        self.last_request: dict[str, object] = {}

    def generate_content(self, **kwargs: object) -> SimpleNamespace:
        """Return a complete schema-compatible multimodal response."""

        self.last_request = kwargs
        payload = {
            "body_language": ["shoulders draw inward"],
            "facial_reaction": ["smile fades slowly"],
            "movement": ["subject freezes"],
            "framing": ["medium close-up"],
            "camera_movement": ["slow push-in"],
            "visual_composition": ["subject isolated at center"],
            "pacing_timing": ["hold the reaction beat"],
            "emotional_progression": ["confidence to embarrassment"],
            "scene_alignment": "Matches the scene's delayed realization.",
            "directing_takeaways": ["Delay the eye movement before the cut."],
        }
        return SimpleNamespace(parsed=payload, text="")


# Wrap fake models in the same shape as the production SDK client.
class FakeClient:
    """Minimal multimodal Gemini test client."""

    def __init__(self) -> None:
        """Expose fake model generation methods."""

        self.models = FakeModels()


# Reuse one representative scene across media-validation tests.
def build_scene() -> Scene:
    """Return a valid screenplay scene for multimodal comparison."""

    return Scene(
        scene_id="scene_001",
        heading="INT. APARTMENT - NIGHT",
        location="APARTMENT",
        time_of_day="NIGHT",
        characters=["JOHN"],
        raw_text="INT. APARTMENT - NIGHT\nJOHN freezes when everyone looks at him.",
    )


# Confirm an image is sent as a media part and parsed into the response schema.
def test_multimodal_image_returns_validated_output() -> None:
    """Analyze an uploaded image reference using a fake Gemini response."""

    client = FakeClient()
    analyzer = MultimodalAnalyzer(client=client, model_name="test-model")
    result = analyzer.analyze(build_scene(), b"image-bytes", "image/png")

    assert result.camera_movement == ["slow push-in"]
    assert result.emotional_progression == ["confidence to embarrassment"]
    assert len(client.models.last_request["contents"]) == 2
    assert len(client.models.last_request["config"].safety_settings) == 4


# Confirm remote video assets use Google's FileData and media-processing pattern.
def test_multimodal_video_uri_returns_validated_output() -> None:
    """Analyze a video URI without downloading the asset into the API process."""

    client = FakeClient()
    analyzer = MultimodalAnalyzer(client=client, model_name="test-model")
    result = analyzer.analyze_uri(
        build_scene(),
        "gs://example-bucket/reference.mp4",
        "video/mp4",
        media_processing="static",
    )

    assert result.scene_alignment.startswith("Matches")
    media_part = client.models.last_request["contents"][1]
    assert media_part.file_data.file_uri == "gs://example-bucket/reference.mp4"
    assert media_part.media_processing == types.MediaProcessing.STATIC


# Confirm nonvisual uploads are rejected before any model request.
def test_multimodal_rejects_unsupported_media() -> None:
    """Reject a reference file outside the image/video allowlist."""

    analyzer = MultimodalAnalyzer(client=FakeClient())
    try:
        analyzer.analyze(build_scene(), b"audio", "audio/mpeg")
    except MultimodalAnalysisError:
        return
    raise AssertionError("Expected unsupported media to be rejected")

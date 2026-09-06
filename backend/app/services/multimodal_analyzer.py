# backend/app/services/multimodal_analyzer.py
"""Reusable Gemini image/video analysis grounded in a screenplay scene."""

import os
from collections.abc import Callable

from google import genai
from google.genai import types
from pydantic import ValidationError

from backend.app.schemas.scene import MultimodalAnalysis, Scene
from backend.app.services.gemini_client import create_gemini_client


# Expose validation and model failures as one service-level error.
class MultimodalAnalysisError(ValueError):
    """Raised when reference media is invalid or cannot be analyzed."""


# Adapt Google's Part-based multimodal example into a production service.
class MultimodalAnalyzer:
    """Analyze an uploaded visual reference alongside a screenplay scene."""

    SUPPORTED_MEDIA_TYPES = {
        "image/jpeg",
        "image/png",
        "image/webp",
        "video/mp4",
        "video/quicktime",
        "video/webm",
    }
    MAX_MEDIA_SIZE = 50 * 1024 * 1024
    SYSTEM_INSTRUCTION = """You are a filmmaking reference analyst. Analyze only visible
and audible evidence in the supplied image or video, then compare it with the screenplay
scene. Describe actionable filmmaking characteristics without identifying private people,
inventing off-screen context, or transcribing the video. Return concise structured data."""

    # Accept an injected client for reuse and isolated tests.
    def __init__(
        self,
        client: genai.Client | None = None,
        model_name: str | None = None,
        client_factory: Callable[[], genai.Client] = create_gemini_client,
    ) -> None:
        """Initialize multimodal analysis with the existing Vertex AI settings."""

        self._client = client
        self._client_factory = client_factory
        self.model_name = model_name or os.getenv(
            "GOOGLE_GENAI_MODEL", "gemini-2.5-flash"
        )

    # Send scene text and inline media as ordered multimodal content parts.
    def analyze(self, scene: Scene, media: bytes, media_type: str) -> MultimodalAnalysis:
        """Extract filmmaking characteristics from an image or video reference."""

        self._validate_media_type(media_type)
        if not media:
            raise MultimodalAnalysisError("The uploaded reference media is empty.")
        if len(media) > self.MAX_MEDIA_SIZE:
            raise MultimodalAnalysisError("The reference media exceeds 50 MB.")

        media_part = types.Part.from_bytes(data=media, mime_type=media_type)
        return self._analyze_part(scene, media_part)

    # Support Cloud Storage and HTTPS media without downloading large assets locally.
    def analyze_uri(
        self,
        scene: Scene,
        media_uri: str,
        media_type: str,
        media_processing: str = "static",
    ) -> MultimodalAnalysis:
        """Analyze a Gemini-accessible image or video URI alongside a scene."""

        self._validate_media_type(media_type)
        if not media_uri.startswith(("gs://", "https://")):
            raise MultimodalAnalysisError(
                "Reference media URI must use gs:// or https://."
            )
        if media_processing not in {"static", "agentic"}:
            raise MultimodalAnalysisError(
                "Video media processing must be static or agentic."
            )

        part_arguments: dict[str, object] = {
            "file_data": types.FileData(
                file_uri=media_uri,
                mime_type=media_type,
            )
        }
        if media_type.startswith("video/"):
            part_arguments["media_processing"] = media_processing
        return self._analyze_part(scene, types.Part(**part_arguments))

    # Keep the scene-grounded prompt and schema configuration identical across sources.
    def _analyze_part(
        self,
        scene: Scene,
        media_part: types.Part,
    ) -> MultimodalAnalysis:
        """Run structured analysis for an already constructed Gemini media part."""

        prompt = (
            "Compare this visual reference with the screenplay scene and extract body "
            "language, facial reaction, movement, framing, camera movement, visual "
            "composition, pacing/timing, emotional progression, alignment, and directing "
            f"takeaways.\n\nSCENE\n{scene.raw_text}"
        )
        try:
            response = self._get_client().models.generate_content(
                model=self.model_name,
                contents=[prompt, media_part],
                config=types.GenerateContentConfig(
                    system_instruction=self.SYSTEM_INSTRUCTION,
                    response_mime_type="application/json",
                    response_schema=MultimodalAnalysis,
                    temperature=0.2,
                ),
            )
            if response.parsed is not None:
                return MultimodalAnalysis.model_validate(response.parsed)
            return MultimodalAnalysis.model_validate_json(response.text)
        except MultimodalAnalysisError:
            raise
        except (ValidationError, ValueError, TypeError, AttributeError) as exc:
            raise MultimodalAnalysisError(
                "Gemini returned invalid structured multimodal output."
            ) from exc
        except Exception as exc:
            raise MultimodalAnalysisError(f"Gemini multimodal analysis failed: {exc}") from exc

    # Apply one allowlist to both inline uploads and URI-based media.
    def _validate_media_type(self, media_type: str) -> None:
        """Reject media types outside the supported image and video set."""

        if media_type not in self.SUPPORTED_MEDIA_TYPES:
            raise MultimodalAnalysisError("Unsupported image or video media type.")

    # Defer Google Cloud authentication until an analysis request is made.
    def _get_client(self) -> genai.Client:
        """Return the shared-style Gemini client, creating it when required."""

        if self._client is None:
            self._client = self._client_factory()
        return self._client

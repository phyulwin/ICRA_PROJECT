# backend/app/agents/script_analyzer.py
"""Structured Gemini Script Intelligence Agent."""

import os
from collections.abc import Callable

from google import genai
from google.genai import types
from pydantic import ValidationError

from backend.app.schemas.scene import Scene, SceneAnalysis
from backend.app.services.gemini_client import create_gemini_client


# Provide a focused exception boundary between Gemini and the HTTP layer.
class ScriptAnalysisError(RuntimeError):
    """Raised when Gemini cannot return valid scene intelligence."""


# Keep the agent reusable and dependency-injectable for deterministic tests.
class ScriptIntelligenceAgent:
    """Analyze screenplay scenes with Gemini and validated Pydantic output."""

    SYSTEM_INSTRUCTION = """You are the Script Intelligence Agent for a cultural-reference director.
Analyze only the supplied scene. Be concise, concrete, and grounded in the screenplay.
Score cultural-reference value from 0 to 100: 0-29 means no reference needed, 30-69
means possible reference opportunity, and 70-100 means strong reference opportunity.
Use the exact matching label. For possible or strong opportunities, return 3-6 diverse
queries, each containing only 3-6 words, for finding existing visual internet artifacts.
Place reaction/meme/clip/GIF/TikTok/Reel/Shorts terminology within those six words. Every query must describe
an observable physical reaction, facial expression, body language, visual action, blocking,
comedic mechanism, or timing and include internet-native vocabulary such as reaction,
meme, viral clip, GIF, TikTok, Reel, or Shorts when appropriate. Seek a comparable
performance moment, not information about the scene topic. Never generate advice,
educational, news, business-blog, listicle, or article-style queries. Do not include site:
filters because the retrieval service adds them. Do not claim a particular meme exists.
For no opportunity, return no queries. Do not search the internet and do not invent facts
about named cultural references."""

    # Accept an optional factory so tests never make external model calls.
    def __init__(
        self,
        client: genai.Client | None = None,
        model_name: str | None = None,
        client_factory: Callable[[], genai.Client] = create_gemini_client,
    ) -> None:
        """Initialize the agent while deferring credentials until first use."""

        self._client = client
        self._client_factory = client_factory
        self.model_name = model_name or os.getenv(
            "GOOGLE_GENAI_MODEL", "gemini-2.5-flash"
        )

    # Request schema-constrained JSON and validate the SDK response defensively.
    def analyze_scene(self, scene: Scene) -> SceneAnalysis:
        """Return structured creative intelligence for one screenplay scene."""

        client = self._get_client()
        prompt = (
            f"Scene ID: {scene.scene_id}\n"
            f"Parsed heading: {scene.heading}\n"
            f"Parsed characters: {', '.join(scene.characters) or 'None detected'}\n\n"
            f"SCREENPLAY SCENE\n{scene.raw_text}"
        )
        try:
            response = client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=self.SYSTEM_INSTRUCTION,
                    response_mime_type="application/json",
                    response_schema=SceneAnalysis,
                    temperature=0.2,
                ),
            )
            if response.parsed is not None:
                return SceneAnalysis.model_validate(response.parsed)
            return SceneAnalysis.model_validate_json(response.text)
        except (ValidationError, ValueError, TypeError, AttributeError) as exc:
            raise ScriptAnalysisError(
                f"Gemini returned invalid structured output for {scene.scene_id}."
            ) from exc
        except Exception as exc:
            raise ScriptAnalysisError(
                f"Gemini analysis failed for {scene.scene_id}: {exc}"
            ) from exc

    # Analyze every parsed scene while preserving screenplay order.
    def analyze_scenes(self, scenes: list[Scene]) -> list[SceneAnalysis]:
        """Analyze a screenplay's scenes in their original order."""

        return [self.analyze_scene(scene) for scene in scenes]

    # Lazily initialize the external SDK client so health checks remain credential-free.
    def _get_client(self) -> genai.Client:
        """Return the configured Gemini client, creating it when required."""

        if self._client is None:
            self._client = self._client_factory()
        return self._client

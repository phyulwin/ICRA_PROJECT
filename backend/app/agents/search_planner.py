# backend/app/agents/search_planner.py
"""Gemini SearchPlan generation grounded in scene intelligence and user intent."""

import json
import os
from collections.abc import Callable

from google import genai
from google.genai import types
from pydantic import ValidationError

from backend.app.schemas.reference import ReferenceSearchPreferences
from backend.app.schemas.scene import Scene, SceneAnalysis
from backend.app.schemas.search_plan import GeminiSearchPlan, SearchPlan
from backend.app.services.gemini_client import create_gemini_client
from backend.app.services.gemini_safety import GEMINI_SAFETY_SETTINGS


# Separate planner validation and provider failures from retrieval errors.
class SearchPlanningError(RuntimeError):
    """Raised when Gemini cannot create a valid diverse SearchPlan."""


# Turn creative intent and preferences into a structured multi-query strategy.
class SearchPlanner:
    """Generate diverse cultural-artifact queries before Parallel Search."""

    SYSTEM_INSTRUCTION = """You plan searches for real visual cultural references.
Combine the screenplay scene, existing analysis, and preferences. The user's natural-
language intent overrides default creative assumptions but never source traceability or
safety. Produce 6-12 genuinely diverse concise queries spanning situation, physical
action, facial reaction, performance, emotional reversal, meme/internet terminology,
platform-specific, and selected reference-type intent. Seek observable artifacts, not
topics. Include negative intents excluding informational articles, advice, tutorials,
business blogs, news commentary, SEO listicles, and generic definitions. Never invent
URLs or claim a result exists. Compact keys: c creative target, m mechanism, v visual
action, p performance, e emotional beat, r desired reference types, t platforms, a era
intent, k ranking priority, q queries, n negative intents, d optional reformulation
diagnosis. Return only structured output."""

    # Keep client creation lazy and injectable for unit coverage.
    def __init__(self, client: genai.Client | None = None, model_name: str | None = None, client_factory: Callable[[], genai.Client] = create_gemini_client) -> None:
        """Configure the existing Vertex Gemini integration."""

        self._client = client
        self._client_factory = client_factory
        self.model_name = model_name or os.getenv("GOOGLE_GENAI_MODEL", "gemini-2.5-flash")

    # Generate one initial or diagnosed reformulation plan with the compact schema.
    def plan(self, scene: Scene, analysis: SceneAnalysis, preferences: ReferenceSearchPreferences, attempted_queries: list[str] | None = None, failure_diagnosis: str | None = None) -> SearchPlan:
        """Return a validated preference-aware SearchPlan."""

        payload = {"scene": scene.model_dump(mode="json"), "scene_analysis": analysis.model_dump(mode="json"), "preferences": preferences.model_dump(mode="json"), "attempted_queries": attempted_queries or [], "failure_diagnosis": failure_diagnosis}
        try:
            response = self._get_client().models.generate_content(model=self.model_name, contents=json.dumps(payload, ensure_ascii=False), config=types.GenerateContentConfig(system_instruction=self.SYSTEM_INSTRUCTION, response_mime_type="application/json", response_schema=GeminiSearchPlan, safety_settings=GEMINI_SAFETY_SETTINGS, temperature=0.25))
            wire = GeminiSearchPlan.model_validate(response.parsed) if response.parsed is not None else GeminiSearchPlan.model_validate_json(response.text)
            return SearchPlan(creative_target=wire.c, comedic_or_dramatic_mechanism=wire.m, desired_visual_action=wire.v, desired_performance=wire.p, desired_emotional_beat=wire.e, desired_reference_types=wire.r, platform_targets=wire.t, era_intent=wire.a, ranking_priority=wire.k, queries=wire.q, negative_intents=wire.n, reformulation_diagnosis=wire.d or failure_diagnosis)
        except (ValidationError, ValueError, TypeError, AttributeError) as exc:
            raise SearchPlanningError("Gemini returned an invalid structured SearchPlan.") from exc
        except Exception as exc:
            raise SearchPlanningError("Gemini search planning is temporarily unavailable.") from exc

    # Create the established Gemini client only for an actual planning request.
    def _get_client(self) -> genai.Client:
        """Return the configured Vertex Gemini client."""

        if self._client is None:
            self._client = self._client_factory()
        return self._client

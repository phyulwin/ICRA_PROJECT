# backend/app/agents/directing_guidance.py
"""Schema-constrained Gemini service for transformative directing guidance."""

import json
import os
from collections.abc import Callable

from google import genai
from google.genai import types
from pydantic import ValidationError

from backend.app.schemas.directing import DirectingGuidance, GeminiDirectingGuidance
from backend.app.schemas.reference import RankedReference
from backend.app.schemas.scene import Scene, SceneAnalysis
from backend.app.services.gemini_client import create_gemini_client
from backend.app.services.gemini_safety import GEMINI_SAFETY_SETTINGS


# Distinguish invalid or blocked model output from client request errors.
class DirectingGuidanceError(RuntimeError):
    """Raised when Gemini cannot return valid reference-grounded guidance."""


# Translate one real ranked reference into original filmmaking direction.
class DirectingGuidanceAgent:
    """Generate actionable guidance from validated scene and reference evidence."""

    SYSTEM_INSTRUCTION = """You are a film director translating cultural references
into original cinematic direction. Analyze why the selected reference works and
translate its underlying performance, visual, timing, and comedic or dramatic principles
into actionable guidance for the supplied screenplay scene. Ground every recommendation
in both the screenplay evidence and the supplied reference assessment. Do not invent
facts beyond the supplied title, snippet, source metadata, artifact evidence, and match
evaluation. Do not reproduce dialogue, copyrighted sequences, or advise shot-for-shot
duplication. Abstract the transferable mechanism. Give concrete actor behavior, staging,
shot size or movement, beat timing, and editing choices. Compact output keys mean:
r reference ID, t reference title, s scene ID, i creative intent, p performance,
f facial expression, b body language, k blocking, c camera, g framing, q shot sequence,
m timing, e editing, u sound, v visual style, w what to borrow, x what not to copy,
and n concise director note. Return only structured output."""

    # Accept dependency injection so tests exercise the production schema without calls.
    def __init__(
        self,
        client: genai.Client | None = None,
        model_name: str | None = None,
        client_factory: Callable[[], genai.Client] = create_gemini_client,
    ) -> None:
        """Initialize a lazy Gemini client using the established model setting."""

        self._client = client
        self._client_factory = client_factory
        self.model_name = model_name or os.getenv("GOOGLE_GENAI_MODEL", "gemini-2.5-flash")

    # Map the compact serving contract into the stable API model.
    @staticmethod
    def _to_guidance(payload: GeminiDirectingGuidance) -> DirectingGuidance:
        """Expand short serving keys after Gemini schema validation."""

        return DirectingGuidance(
            reference_id=payload.r,
            reference_title=payload.t,
            scene_id=payload.s,
            creative_intent=payload.i,
            performance=payload.p,
            facial_expression=payload.f,
            body_language=payload.b,
            blocking=payload.k,
            camera=payload.c,
            framing=payload.g,
            shot_sequence=payload.q,
            timing=payload.m,
            editing=payload.e,
            sound=payload.u,
            visual_style=payload.v,
            what_to_borrow=payload.w,
            what_not_to_copy=payload.x,
            concise_director_note=payload.n,
        )

    # Send only validated screenplay and persisted Parallel/Gemini evidence to Gemini.
    def generate(
        self,
        scene: Scene,
        analysis: SceneAnalysis,
        selected_reference: RankedReference,
    ) -> DirectingGuidance:
        """Return structured, IP-safe directing guidance for one selected reference."""

        payload = {
            "scene": scene.model_dump(mode="json"),
            "scene_analysis": analysis.model_dump(mode="json"),
            "selected_reference": selected_reference.model_dump(mode="json"),
        }
        try:
            response = self._get_client().models.generate_content(
                model=self.model_name,
                contents=json.dumps(payload, ensure_ascii=False),
                config=types.GenerateContentConfig(
                    system_instruction=self.SYSTEM_INSTRUCTION,
                    response_mime_type="application/json",
                    response_schema=GeminiDirectingGuidance,
                    safety_settings=GEMINI_SAFETY_SETTINGS,
                    temperature=0.25,
                ),
            )
            compact = (
                GeminiDirectingGuidance.model_validate(response.parsed)
                if response.parsed is not None
                else GeminiDirectingGuidance.model_validate_json(response.text)
            )
            guidance = self._to_guidance(compact)
            if guidance.scene_id != scene.scene_id:
                raise ValueError("Gemini returned guidance for a different scene")
            if guidance.reference_id != selected_reference.reference.id:
                raise ValueError("Gemini returned guidance for a different reference")
            return guidance
        except (ValidationError, ValueError, TypeError, AttributeError) as exc:
            raise DirectingGuidanceError(
                "Gemini returned invalid structured directing guidance."
            ) from exc
        except Exception as exc:
            raise DirectingGuidanceError(
                "Gemini directing guidance is temporarily unavailable."
            ) from exc

    # Defer external client creation so health and Firestore routes remain lightweight.
    def _get_client(self) -> genai.Client:
        """Return the configured Gemini client, creating it only when required."""

        if self._client is None:
            self._client = self._client_factory()
        return self._client

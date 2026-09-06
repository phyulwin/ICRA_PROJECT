# backend/app/services/agent_engine_service.py
"""Production gateway from Cloud Run to the deployed ADK Agent Engine."""

import os
from typing import Any
from uuid import uuid4

import vertexai
from pydantic import ValidationError
from vertexai import agent_engines

from backend.app.adk.state import ProjectSessionState
from backend.app.schemas.reference import (
    CulturalSearchResult,
    RankedReference,
    ReferenceSearchRequest,
    ReferenceSearchResponse,
)
from backend.app.schemas.scene import Scene, SceneAnalysis


# Keep managed-agent failures distinct so the API can sanitize them consistently.
class AgentEngineInvocationError(RuntimeError):
    """Raised when the managed ADK workflow does not return a valid tool result."""

    def __init__(self, message: str, status_code: int = 502) -> None:
        """Store one safe public message and its HTTP mapping."""

        super().__init__(message)
        self.status_code = status_code


# Centralize managed-session creation and typed function-response extraction.
class AgentEngineGateway:
    """Invoke the deployed Agent Engine while preserving Pydantic API contracts."""

    def __init__(self) -> None:
        """Defer SDK initialization until a production request needs it."""

        self.enabled = os.getenv("USE_AGENT_ENGINE", "False").lower() in {
            "1",
            "true",
            "yes",
        }
        self._remote_agent: Any | None = None

    # Ask the managed agent for exactly one validated scene-analysis tool result.
    async def analyze_scene(self, scene: Scene) -> SceneAnalysis:
        """Return Agent Engine's structured analyze_scene function response."""

        state = ProjectSessionState(
            selected_scene_id=scene.scene_id,
            scene=scene,
        )
        results = await self._invoke(
            state,
            "Call analyze_scene exactly once with this validated scene JSON: "
            f"{scene.model_dump_json()}. Do not call search_cultural_references, "
            "rank_references, or any other tool in this request. Return only a "
            "concise completion after analyze_scene succeeds.",
        )
        payload = results.get("analyze_scene", {})
        try:
            return SceneAnalysis.model_validate(payload["scene_analysis"])
        except (KeyError, TypeError, ValidationError) as exc:
            raise AgentEngineInvocationError(
                "The managed scene-analysis service returned an invalid result."
            ) from exc

    # Run live retrieval and ranking inside the deployed ADK boundary.
    async def find_references(
        self,
        request: ReferenceSearchRequest,
    ) -> ReferenceSearchResponse:
        """Return validated Parallel discovery and Gemini ranking from Agent Engine."""

        state = ProjectSessionState(
            selected_scene_id=request.scene.scene_id,
            scene=request.scene,
            scene_analysis=request.scene_analysis,
            search_preferences=request.preferences,
            search_queries=request.scene_analysis.reference_queries,
        )
        preferences = request.preferences
        message = (
            "Use search_cultural_references exactly once with these preferences: "
            f"reference_type={preferences.reference_type.value}, "
            f"era={preferences.era.value}, match_for={preferences.match_for.value}, "
            f"obscurity={preferences.obscurity}, max_results={preferences.max_results}. "
            "Then call rank_references exactly once when candidates exist. Do not "
            "reanalyze the scene and do not invent results."
        )
        results = await self._invoke(state, message)
        search_payload = results.get("search_cultural_references")
        if not isinstance(search_payload, dict):
            raise AgentEngineInvocationError(
                "The managed reference-search service returned no result."
            )

        try:
            search_result = CulturalSearchResult.model_validate(
                {
                    "candidates": search_payload.get("candidates", []),
                    "searched_queries": search_payload.get("searched_queries", []),
                    "failed_queries": search_payload.get("failed_queries", []),
                    "warnings": search_payload.get("warnings", []),
                    "raw_candidate_count": search_payload.get("raw_candidate_count", 0),
                    "rejected_candidate_count": search_payload.get(
                        "rejected_candidate_count", 0
                    ),
                    "extracted_candidate_count": search_payload.get(
                        "extracted_candidate_count", 0
                    ),
                    "retry_count": search_payload.get("retry_count", 0),
                }
            )
            rank_payload = results.get("rank_references", {})
            ranked = [
                RankedReference.model_validate(item)
                for item in rank_payload.get("ranked_references", [])
            ]
            return ReferenceSearchResponse(
                scene_id=request.scene.scene_id,
                references=ranked,
                raw_candidate_count=search_result.raw_candidate_count,
                rejected_candidate_count=search_result.rejected_candidate_count,
                extracted_candidate_count=search_result.extracted_candidate_count,
                searched_queries=search_result.searched_queries,
                failed_queries=search_result.failed_queries,
                warnings=search_result.warnings,
                partial_success=search_result.partial_success,
                retry_count=search_result.retry_count,
            )
        except (TypeError, ValidationError) as exc:
            raise AgentEngineInvocationError(
                "The managed reference service returned an invalid result."
            ) from exc

    # Create an isolated managed session and retain only genuine function responses.
    async def _invoke(
        self,
        state: ProjectSessionState,
        message: str,
    ) -> dict[str, dict[str, Any]]:
        """Stream one managed request and return tool responses by function name."""

        try:
            remote_agent = self._get_remote_agent()
            user_id = f"cloud_run_{uuid4().hex}"
            session = await remote_agent.async_create_session(
                user_id=user_id,
                state=state.model_dump(mode="json"),
            )
            session_id = session["id"] if isinstance(session, dict) else session.id
            responses: dict[str, dict[str, Any]] = {}
            async for event in remote_agent.async_stream_query(
                user_id=user_id,
                session_id=session_id,
                message=message,
            ):
                if isinstance(event, dict) and event.get("errorCode"):
                    raise AgentEngineInvocationError(
                        "The managed agent could not complete the request."
                    )
                content = event.get("content", {}) if isinstance(event, dict) else {}
                for part in content.get("parts", []):
                    function_response = part.get("functionResponse") or part.get(
                        "function_response"
                    )
                    if not function_response:
                        continue
                    name = function_response.get("name", "")
                    response = function_response.get("response", {})
                    if name and isinstance(response, dict):
                        responses[name] = response
            return responses
        except AgentEngineInvocationError:
            raise
        except TimeoutError as exc:
            raise AgentEngineInvocationError(
                "The managed agent timed out.", status_code=504
            ) from exc
        except Exception as exc:
            raise AgentEngineInvocationError(
                "The managed agent is temporarily unavailable."
            ) from exc

    # Resolve the configured reasoning engine without storing credentials in-process.
    def _get_remote_agent(self) -> Any:
        """Return the lazily initialized Vertex AI reasoning engine client."""

        if self._remote_agent is not None:
            return self._remote_agent
        project = os.getenv("GOOGLE_CLOUD_PROJECT", "").strip()
        location = os.getenv("AGENT_ENGINE_LOCATION", "us-central1").strip()
        resource_name = os.getenv("AGENT_ENGINE_RESOURCE_NAME", "").strip()
        if not project or not resource_name:
            raise AgentEngineInvocationError(
                "The managed agent configuration is incomplete.", status_code=503
            )
        try:
            vertexai.init(project=project, location=location)
            self._remote_agent = agent_engines.get(resource_name)
            return self._remote_agent
        except Exception as exc:
            raise AgentEngineInvocationError(
                "The managed agent configuration could not be initialized.",
                status_code=503,
            ) from exc

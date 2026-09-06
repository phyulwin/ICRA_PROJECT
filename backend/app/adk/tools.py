# backend/app/adk/tools.py
"""Thin ADK tools over the project's established production services."""

from google.adk.tools import ToolContext

from backend.app.agents.culture_search import CulturalSearchAgent
from backend.app.agents.reference_ranker import ReferenceRanker
from backend.app.agents.script_analyzer import ScriptIntelligenceAgent
from backend.app.schemas.reference import (
    MatchFor,
    ReferenceEra,
    ReferenceSearchPreferences,
    ReferenceType,
)
from backend.app.schemas.scene import Scene, SceneAnalysis
from backend.app.services.multimodal_analyzer import MultimodalAnalyzer
from backend.app.services.reference_preview import ReferencePreviewResolver
from backend.app.services.reference_quality import build_artifact_queries
from backend.app.adk.state import (
    SearchHistoryEntry,
    ToolStatus,
    load_project_state,
    save_project_state,
)


# Keep service construction lazy so health checks and ADK discovery need no credentials.
def _script_agent() -> ScriptIntelligenceAgent:
    """Construct the existing structured screenplay-analysis service."""

    return ScriptIntelligenceAgent()


# Keep the live Parallel client behind the established search agent boundary.
def _search_agent() -> CulturalSearchAgent:
    """Construct the existing Parallel-backed cultural search service."""

    return CulturalSearchAgent()


# Preserve Gemini assessment and deterministic application-owned scoring.
def _reference_ranker() -> ReferenceRanker:
    """Construct the existing reference ranker."""

    return ReferenceRanker()


# Reuse the existing image/video Gemini implementation.
def _multimodal_analyzer() -> MultimodalAnalyzer:
    """Construct the existing multimodal service."""

    return MultimodalAnalyzer()


# Expose Gemini scene analysis as one genuine ADK function tool.
def analyze_scene(scene: Scene, tool_context: ToolContext) -> dict:
    """Analyze one parsed screenplay scene and return validated scene intelligence."""

    try:
        validated_scene = Scene.model_validate(scene)
        analysis = _script_agent().analyze_scene(validated_scene)
        state = load_project_state(tool_context.state)
        state.selected_scene_id = validated_scene.scene_id
        state.scene = validated_scene
        state.scene_analysis = analysis
        state.search_queries = analysis.reference_queries
        state.last_tool_status = ToolStatus(
            tool_name="analyze_scene", status="success"
        )
        save_project_state(state, tool_context.state)
        return {
            "status": "success",
            "scene_analysis": analysis.model_dump(mode="json"),
            "result_count": 1,
        }
    except Exception:
        raise


# Expose the only permitted live-reference source through a bounded search tool.
def search_cultural_references(
    tool_context: ToolContext,
    reference_type: ReferenceType = ReferenceType.ALL,
    era: ReferenceEra = ReferenceEra.ANY,
    match_for: MatchFor = MatchFor.ALL,
    obscurity: int = 50,
    max_results: int = 6,
) -> dict:
    """Search real cultural references through Parallel with at most one retry."""

    try:
        state = load_project_state(tool_context.state)
        if state.scene is None or state.scene_analysis is None:
            raise ValueError("analyze_scene must succeed before reference search.")
        validated_scene = state.scene
        validated_analysis = state.scene_analysis
        preferences = ReferenceSearchPreferences.model_validate(
            {
                "reference_type": reference_type,
                "era": era,
                "match_for": match_for,
                "obscurity": obscurity,
                "max_results": max_results,
            }
        )
        result = _search_agent().search(
            validated_scene,
            validated_analysis,
            preferences,
        )
        initial_queries = build_artifact_queries(
            validated_analysis.reference_queries,
            preferences.reference_type,
        )
        retry_count = int(len(result.searched_queries) > len(initial_queries))
        state.scene = validated_scene
        state.scene_analysis = validated_analysis
        state.search_preferences = preferences
        state.search_queries = result.searched_queries
        state.retry_count = min(retry_count, 1)
        state.raw_reference_candidates = result.candidates
        state.search_history.append(
            SearchHistoryEntry(
                queries=result.searched_queries,
                candidate_count=len(result.candidates),
                status="partial_success" if result.partial_success else "success",
            )
        )
        state.last_tool_status = ToolStatus(
            tool_name="search_cultural_references",
            status="partial_success" if result.partial_success else "success",
        )
        save_project_state(state, tool_context.state)
        return {
            "status": "partial_success" if result.partial_success else "success",
            "candidates": [
                candidate.model_dump(mode="json") for candidate in result.candidates
            ],
            "searched_queries": result.searched_queries,
            "failed_queries": [
                failure.model_dump(mode="json") for failure in result.failed_queries
            ],
            "warnings": result.warnings,
            "raw_candidate_count": result.raw_candidate_count,
            "rejected_candidate_count": result.rejected_candidate_count,
            "extracted_candidate_count": result.extracted_candidate_count,
            "retry_count": min(retry_count, 1),
            "result_count": len(result.candidates),
        }
    except Exception:
        raise


# Expose Gemini evaluation followed by deterministic local ranking.
def rank_references(
    tool_context: ToolContext,
) -> dict:
    """Evaluate only supplied Parallel candidates and rank them deterministically."""

    try:
        state = load_project_state(tool_context.state)
        if state.scene is None or state.scene_analysis is None:
            raise ValueError("analyze_scene must succeed before reference ranking.")
        if not state.raw_reference_candidates:
            raise ValueError("search_cultural_references must succeed before ranking.")
        validated_scene = state.scene
        validated_analysis = state.scene_analysis
        validated_candidates = state.raw_reference_candidates
        preferences = state.search_preferences
        ranked = _reference_ranker().rank(
            validated_scene,
            validated_analysis,
            validated_candidates,
            preferences,
        )
        enriched = ReferencePreviewResolver().enrich_ranked_references(ranked)
        state.ranked_references = enriched
        state.last_tool_status = ToolStatus(
            tool_name="rank_references", status="success"
        )
        save_project_state(state, tool_context.state)
        return {
            "status": "success",
            "ranked_references": [
                reference.model_dump(mode="json") for reference in enriched
            ],
            "result_count": len(enriched),
        }
    except Exception:
        raise


# Use URI-based multimodal input so binary payloads never enter session state.
def analyze_multimodal_reference(
    media_uri: str,
    media_type: str,
    tool_context: ToolContext,
) -> dict:
    """Analyze an image or video URI against a screenplay scene with Gemini."""

    try:
        state = load_project_state(tool_context.state)
        if state.scene is None:
            raise ValueError("analyze_scene must succeed before multimodal analysis.")
        validated_scene = state.scene
        analysis = _multimodal_analyzer().analyze_uri(
            validated_scene,
            media_uri,
            media_type,
        )
        state.scene = validated_scene
        state.last_tool_status = ToolStatus(
            tool_name="analyze_multimodal_reference", status="success"
        )
        save_project_state(state, tool_context.state)
        return {
            "status": "success",
            "analysis": analysis.model_dump(mode="json"),
            "result_count": 1,
        }
    except Exception:
        raise

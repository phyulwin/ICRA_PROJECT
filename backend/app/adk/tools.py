# backend/app/adk/tools.py
"""Thin ADK tools over the project's established production services."""

from google.adk.tools import ToolContext

from backend.app.agents.culture_search import CulturalSearchAgent
from backend.app.agents.directing_guidance import DirectingGuidanceAgent
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
from backend.app.tools.parallel_search import deduplicate_candidates
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


# Preserve the established Gemini client, schemas, and safety settings for direction.
def _directing_agent() -> DirectingGuidanceAgent:
    """Construct the structured directing-guidance service."""

    return DirectingGuidanceAgent()


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
    match_for: MatchFor = MatchFor.BEST_OVERALL,
    recognition: int = 50,
    user_intent: str = "",
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
                "recognition": recognition,
                "user_intent": user_intent,
                "max_results": max_results,
            }
        )
        result = _search_agent().search(
            validated_scene,
            validated_analysis,
            preferences,
            allow_artifact_retry=False,
        )
        retry_count = result.retry_count
        state.scene = validated_scene
        state.scene_analysis = validated_analysis
        state.search_preferences = preferences
        state.search_queries = result.searched_queries
        state.search_plan = result.search_plan
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
            "search_plan": result.search_plan.model_dump(mode="json") if result.search_plan else None,
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
            state.search_plan,
        )
        # Diagnose and reformulate once only after the first ranked-quality signal.
        if len(ranked) < 3 and state.retry_count == 0:
            refined = _search_agent().search(
                validated_scene,
                validated_analysis,
                preferences,
                attempted_queries=state.search_queries,
                failure_diagnosis=(
                    "Fewer than three candidates passed artifact and creative-match "
                    "thresholds; seek observable behavior rather than topic pages."
                ),
                allow_artifact_retry=False,
            )
            validated_candidates = deduplicate_candidates([*validated_candidates, *refined.candidates], limit=24)
            ranked = _reference_ranker().rank(validated_scene, validated_analysis, validated_candidates, preferences, refined.search_plan)
            state.raw_reference_candidates = validated_candidates
            state.search_queries = [*state.search_queries, *refined.searched_queries]
            state.search_plan = refined.search_plan
            state.retry_count = 1
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
            "searched_queries": state.search_queries,
            "retry_count": state.retry_count,
            "search_plan": state.search_plan.model_dump(mode="json") if state.search_plan else None,
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


# Translate the selected real reference without rerunning retrieval or ranking.
def generate_directing_guidance(tool_context: ToolContext) -> dict:
    """Generate structured directing guidance from verified session state."""

    try:
        state = load_project_state(tool_context.state)
        if state.scene is None or state.scene_analysis is None:
            raise ValueError("Scene analysis is required before directing guidance.")
        if state.selected_reference is None:
            raise ValueError("A ranked reference must be selected before guidance.")
        guidance = _directing_agent().generate(
            state.scene,
            state.scene_analysis,
            state.selected_reference,
        )
        state.directing_guidance = guidance
        state.last_tool_status = ToolStatus(
            tool_name="generate_directing_guidance",
            status="success",
        )
        save_project_state(state, tool_context.state)
        return {
            "status": "success",
            "directing_guidance": guidance.model_dump(mode="json"),
            "result_count": 1,
        }
    except Exception:
        raise

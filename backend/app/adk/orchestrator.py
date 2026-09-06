# backend/app/adk/orchestrator.py
"""Deterministic API orchestration over existing search and ranking services."""

import logging
from time import monotonic

from backend.app.agents.culture_search import CulturalSearchAgent
from backend.app.agents.reference_ranker import ReferenceRanker
from backend.app.schemas.reference import (
    ReferenceSearchRequest,
    ReferenceSearchResponse,
)
from backend.app.schemas.scene import ReferenceOpportunity
from backend.app.services.reference_preview import ReferencePreviewResolver


logger = logging.getLogger("cultural_reference_director.workflow")


# Keep the production HTTP workflow predictable while sharing the ADK service boundary.
class ReferenceWorkflowOrchestrator:
    """Run Parallel discovery, Gemini evaluation, and deterministic ranking."""

    def __init__(
        self,
        search_agent: CulturalSearchAgent | None = None,
        ranker: ReferenceRanker | None = None,
        preview_resolver: ReferencePreviewResolver | None = None,
    ) -> None:
        """Initialize reusable dependencies without making external calls."""

        self._search_agent = search_agent or CulturalSearchAgent()
        self._ranker = ranker or ReferenceRanker()
        self._preview_resolver = preview_resolver or ReferencePreviewResolver()

    def find_references(
        self,
        request: ReferenceSearchRequest,
        *,
        explicit_search: bool = False,
    ) -> ReferenceSearchResponse:
        """Execute the invariant workflow and skip unsuitable scenes by default."""

        started_at = monotonic()
        if (
            request.scene_analysis.reference_opportunity == ReferenceOpportunity.NONE
            and not explicit_search
        ):
            logger.info(
                "reference_workflow_skipped",
                extra={"scene_id": request.scene.scene_id, "reason": "no_opportunity"},
            )
            return ReferenceSearchResponse(
                scene_id=request.scene.scene_id,
                references=[],
                raw_candidate_count=0,
                searched_queries=[],
                warnings=["Reference search skipped for a no-reference scene."],
            )

        try:
            search_result = self._search_agent.search(
                request.scene,
                request.scene_analysis,
                request.preferences,
            )
            ranked = self._ranker.rank(
                request.scene,
                request.scene_analysis,
                search_result.candidates,
                request.preferences,
            )
            ranked = self._preview_resolver.enrich_ranked_references(ranked)
            response = ReferenceSearchResponse(
                scene_id=request.scene.scene_id,
                references=ranked,
                raw_candidate_count=search_result.raw_candidate_count,
                rejected_candidate_count=max(
                    search_result.rejected_candidate_count,
                    search_result.raw_candidate_count - len(ranked),
                ),
                extracted_candidate_count=search_result.extracted_candidate_count,
                searched_queries=search_result.searched_queries,
                failed_queries=search_result.failed_queries,
                warnings=search_result.warnings,
                partial_success=search_result.partial_success,
            )
            logger.info(
                "reference_workflow_complete",
                extra={
                    "scene_id": request.scene.scene_id,
                    "candidate_count": search_result.raw_candidate_count,
                    "ranked_count": len(ranked),
                    "duration_ms": round((monotonic() - started_at) * 1000),
                },
            )
            return response
        except Exception as exc:
            logger.exception(
                "reference_workflow_error",
                extra={
                    "scene_id": request.scene.scene_id,
                    "error_type": type(exc).__name__,
                },
            )
            raise

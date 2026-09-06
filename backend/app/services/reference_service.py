# backend/app/services/reference_service.py
"""Compatibility service delegating Phase 3 to the ADK workflow boundary."""

from backend.app.adk.orchestrator import ReferenceWorkflowOrchestrator
from backend.app.agents.culture_search import CulturalSearchAgent
from backend.app.agents.reference_ranker import ReferenceRanker
from backend.app.schemas.reference import (
    ReferenceSearchRequest,
    ReferenceSearchResponse,
)
from backend.app.services.reference_preview import ReferencePreviewResolver


# Keep the endpoint thin and make the complete Phase 3 workflow testable.
class ReferenceDiscoveryService:
    """Run Parallel discovery followed by Gemini assessment and local ranking."""

    # Accept agent dependencies for endpoint and integration tests.
    def __init__(
        self,
        search_agent: CulturalSearchAgent | None = None,
        ranker: ReferenceRanker | None = None,
        preview_resolver: ReferencePreviewResolver | None = None,
    ) -> None:
        """Initialize the reference-discovery workflow."""

        self._orchestrator = ReferenceWorkflowOrchestrator(
            search_agent=search_agent,
            ranker=ranker,
            preview_resolver=preview_resolver,
        )

    # Reuse the supplied Phase 2 result and never rerun scene analysis.
    def find_references(
        self,
        request: ReferenceSearchRequest,
    ) -> ReferenceSearchResponse:
        """Discover, assess, and rank traceable cultural references."""

        return self._orchestrator.find_references(request, explicit_search=True)

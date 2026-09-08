# backend/tests/test_adk_architecture.py
"""Tests for native ADK tools, state, and deterministic API orchestration."""

import asyncio
from types import SimpleNamespace

from google.adk.tools import FunctionTool

import backend.app.adk.tools as adk_tools
from backend.app.adk.orchestrator import ReferenceWorkflowOrchestrator
from backend.app.adk.root_agent import root_agent
from backend.app.agents.culture_search import CulturalSearchAgent
from backend.app.schemas.reference import (
    CulturalReferenceCandidate,
    CulturalReferenceType,
    CulturalSearchResult,
    RankedReference,
    ReferenceAssessment,
    ReferenceSearchRequest,
    ReferenceType,
    SourcePlatform,
)
from backend.app.schemas.scene import SceneAnalysis
from backend.app.schemas.search_plan import SearchPlan


# Build one complete production-shaped request for orchestration tests.
def build_request(opportunity: str = "strong reference opportunity") -> ReferenceSearchRequest:
    """Return valid scene intelligence and browser search preferences."""

    score = 85 if opportunity == "strong reference opportunity" else 10
    queries = [
        "caught lying reaction meme",
        "awkward realization viral clip",
        "guilty face reaction GIF",
    ] if score >= 30 else []
    return ReferenceSearchRequest.model_validate(
        {
            "scene": {
                "scene_id": "scene_001",
                "heading": "INT. APARTMENT - NIGHT",
                "location": "APARTMENT",
                "time_of_day": "NIGHT",
                "characters": ["JOHN"],
                "raw_text": "INT. APARTMENT - NIGHT\nJOHN stops smiling.",
            },
            "scene_analysis": {
                "scene_type": "comedy",
                "tone": ["awkward"],
                "characters": ["JOHN"],
                "character_intentions": [
                    {"character": "JOHN", "intention": "hide the lie"}
                ],
                "primary_beat": "John realizes he was caught",
                "emotions": ["embarrassment"],
                "comedic_or_dramatic_mechanism": "delayed realization",
                "important_actions": ["John stops smiling"],
                "visual_characteristics": ["frozen reaction"],
                "cultural_concepts": ["caught in a lie"],
                "reference_opportunity": opportunity,
                "reference_opportunity_score": score,
                "reference_opportunity_reason": "A reaction can guide performance.",
                "reference_queries": queries,
            },
        }
    )


# Construct one traceable candidate that retains provider-owned source metadata.
def build_candidate() -> CulturalReferenceCandidate:
    """Return a real-source-shaped Parallel candidate."""

    return CulturalReferenceCandidate(
        id="parallel_001",
        title="Verified reaction clip",
        url="https://example.com/reaction",
        source_domain="example.com",
        snippet="A visible delayed reaction.",
        reference_type=ReferenceType.FILM,
        cultural_reference_type=CulturalReferenceType.FILM_TV_MOMENT,
        source_platform=SourcePlatform.FILM_TV,
        discovered_from_query="caught lying reaction meme",
        source_metadata={"provider": "parallel", "session_id": "session_123"},
    )


# Capture orchestration order while returning a real search-result contract.
class FakeSearchAgent:
    """Return one candidate and record that search occurred."""

    def __init__(self, calls: list[str]) -> None:
        """Retain the shared sequence recorder."""

        self.calls = calls

    def search(self, scene: object, analysis: object, preferences: object, **kwargs: object) -> CulturalSearchResult:
        """Simulate a successful Parallel round."""

        self.calls.append("search")
        return CulturalSearchResult(
            candidates=[build_candidate()],
            searched_queries=["caught lying reaction meme"],
            raw_candidate_count=1,
        )


# Return deterministic ranking while preserving the candidate object.
class FakeRanker:
    """Record ranking after search and return one ranked reference."""

    def __init__(self, calls: list[str]) -> None:
        """Retain the shared sequence recorder."""

        self.calls = calls

    def rank(self, scene: object, analysis: object, candidates: list, preferences: object, search_plan: object = None) -> list[RankedReference]:
        """Build a deterministic result from the supplied candidate."""

        self.calls.append("rank")
        assessment = ReferenceAssessment(
            candidate_id=candidates[0].id,
            emotional_similarity=80,
            situational_similarity=80,
            visual_similarity=80,
            acting_similarity=80,
            timing_similarity=80,
            recognizability=80,
            cultural_relevance=80,
            artifact_verified=True,
            cultural_reference_type=CulturalReferenceType.FILM_TV_MOMENT,
            artifact_quality=80,
            artifact_evidence="Direct clip evidence.",
            match_reason="The visible reaction aligns.",
        )
        return [
            RankedReference(
                reference=candidates[0],
                assessment=assessment,
                overall_score=80,
            )
        ]


# Avoid network preview resolution in orchestration tests.
class FakePreviewResolver:
    """Return ranked references unchanged."""

    def enrich_ranked_references(self, references: list[RankedReference]) -> list[RankedReference]:
        """Preserve source metadata without external HTTP calls."""

        return references


# Simulate two provider rounds so the established retry ceiling is measurable.
class FakeRetryParallelClient:
    """Return weak initial retrieval followed by one improved round."""

    def __init__(self) -> None:
        """Initialize the provider call counter."""

        self.call_count = 0

    def search_cultural_references(self, **kwargs: object) -> CulturalSearchResult:
        """Return no candidates first and one candidate on the retry."""

        self.call_count += 1
        candidates = [build_candidate()] if self.call_count == 2 else []
        return CulturalSearchResult(
            candidates=candidates,
            searched_queries=list(kwargs["queries"]),
            raw_candidate_count=len(candidates),
        )

    def enrich_ambiguous_candidates(
        self,
        candidates: list[CulturalReferenceCandidate],
        **kwargs: object,
    ) -> tuple[list[CulturalReferenceCandidate], list[str], int]:
        """Return direct candidates unchanged after search."""

        return candidates, [], 0


# Provide the schema-constrained query reformulation response used by the retry.
class FakeReformulationClient:
    """Expose the Gemini models surface for one query rewrite."""

    def __init__(self) -> None:
        """Build a minimal models namespace."""

        self.models = SimpleNamespace(generate_content=self.generate_content)

    def generate_content(self, **kwargs: object) -> SimpleNamespace:
        """Return three bounded replacement queries."""

        return SimpleNamespace(
            parsed={
                "queries": [
                    "office mistake reaction GIF",
                    "public embarrassment viral clip",
                    "frozen panic reaction meme",
                ]
            },
            text="",
        )


# Supply deterministic v2 plans while keeping retrieval tests network-free.
class FakeSearchPlanner:
    """Return diverse initial and diagnosed fallback plans."""

    def plan(self, scene: object, analysis: object, preferences: object, attempted_queries: list[str] | None = None, failure_diagnosis: str | None = None) -> SearchPlan:
        """Build a complete SearchPlan for the requested round."""

        suffix = "refined" if attempted_queries else "initial"
        return SearchPlan(creative_target="visible caught-lie reaction", comedic_or_dramatic_mechanism="delayed realization", desired_visual_action="smile freezes", desired_performance="confidence collapses", desired_emotional_beat="embarrassment", desired_reference_types=["reaction meme"], platform_targets=["Tenor"], era_intent="any", ranking_priority="best overall", queries=[f"{suffix} caught lying reaction meme", f"{suffix} guilty face reaction gif", f"{suffix} awkward realization viral clip", f"{suffix} frozen smile comedy moment", f"{suffix} embarrassed performance reaction", f"{suffix} everyone knows silent stare"], negative_intents=["articles", "advice", "tutorials"], reformulation_diagnosis=failure_diagnosis)


# Verify the conventional ADK entrypoint exposes genuine callable tools.
def test_root_agent_registers_real_function_tools() -> None:
    """Register each established capability on the root ADK agent."""

    names = [tool.__name__ for tool in root_agent.tools]
    assert names == [
        "analyze_scene",
        "search_cultural_references",
        "rank_references",
        "generate_directing_guidance",
        "analyze_multimodal_reference",
    ]


# Execute a real ADK FunctionTool wrapper and validate durable session state.
def test_analyze_scene_function_tool_invokes_service(monkeypatch: object) -> None:
    """Invoke the ADK tool machinery rather than merely calling a mock endpoint."""

    request = build_request()
    expected = request.scene_analysis
    fake_agent = SimpleNamespace(analyze_scene=lambda scene: expected)
    monkeypatch.setattr(adk_tools, "_script_agent", lambda: fake_agent)
    context = SimpleNamespace(state={})
    function_tool = FunctionTool(adk_tools.analyze_scene)

    response = asyncio.run(
        function_tool.run_async(
            args={"scene": request.scene.model_dump(mode="json")},
            tool_context=context,
        )
    )

    assert response["scene_analysis"]["primary_beat"] == expected.primary_beat
    assert context.state["selected_scene_id"] == "scene_001"
    assert context.state["last_tool_status"]["status"] == "success"


# Prove search precedes ranking and provider metadata survives the workflow.
def test_orchestrator_sequences_search_then_rank_and_preserves_source() -> None:
    """Execute the required invariant order with immutable source facts."""

    calls: list[str] = []
    orchestrator = ReferenceWorkflowOrchestrator(
        search_agent=FakeSearchAgent(calls),
        ranker=FakeRanker(calls),
        preview_resolver=FakePreviewResolver(),
    )

    response = orchestrator.find_references(build_request())

    assert calls == ["search", "rank", "search", "rank"]
    assert response.references[0].reference.source_metadata == {
        "provider": "parallel",
        "session_id": "session_123",
    }


# Enforce the default no-search branch for scenes with no reference opportunity.
def test_orchestrator_skips_no_reference_scene() -> None:
    """Avoid Parallel and ranking calls until the user explicitly requests them."""

    calls: list[str] = []
    orchestrator = ReferenceWorkflowOrchestrator(
        search_agent=FakeSearchAgent(calls),
        ranker=FakeRanker(calls),
        preview_resolver=FakePreviewResolver(),
    )

    response = orchestrator.find_references(build_request("no reference needed"))

    assert calls == []
    assert response.references == []
    assert response.searched_queries == []


# Prove weak retrieval performs one retry and never enters an open-ended loop.
def test_cultural_search_retries_exactly_once() -> None:
    """Bound provider search to an initial round plus one reformulation round."""

    provider = FakeRetryParallelClient()
    agent = CulturalSearchAgent(
        parallel_search=provider,
        gemini_client=FakeReformulationClient(),
        search_planner=FakeSearchPlanner(),
    )
    request = build_request()

    result = agent.search(
        request.scene,
        request.scene_analysis,
        request.preferences,
    )

    assert provider.call_count == 2
    assert result.candidates[0].id == "parallel_001"

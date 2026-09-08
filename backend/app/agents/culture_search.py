# backend/app/agents/culture_search.py
"""Cultural Search Agent coordinating Gemini intent with Parallel retrieval."""

import os
from collections.abc import Callable
from uuid import uuid4

from google import genai
from google.genai import types
from pydantic import ValidationError

from backend.app.agents.search_planner import SearchPlanner
from backend.app.schemas.reference import (
    CulturalSearchResult,
    QueryReformulation,
    ReferenceSearchPreferences,
)
from backend.app.schemas.scene import Scene, SceneAnalysis
from backend.app.services.gemini_client import create_gemini_client
from backend.app.services.gemini_safety import GEMINI_SAFETY_SETTINGS
from backend.app.services.reference_quality import (
    count_direct_artifacts,
    filter_informational_candidates,
    prioritize_artifacts,
)
from backend.app.tools.parallel_search import (
    ParallelSearchClient,
    deduplicate_candidates,
)


# Keep search-orchestration failures separate from provider failures.
class CulturalSearchError(RuntimeError):
    """Raised when cultural search orchestration cannot produce a valid outcome."""


# Coordinate existing Phase 2 intent with real Parallel Search results.
class CulturalSearchAgent:
    """Search cultural references using scene queries and user preferences."""

    MIN_ARTIFACTS_BEFORE_REFORMULATION = 3
    RAW_CANDIDATE_LIMIT = 24
    SYSTEM_INSTRUCTION = """You improve weak visual-cultural-reference searches.
Return three concise keyword queries of three to six words. Each query must seek an
existing observable internet moment through physical reaction, facial expression, body
language, blocking, visual action, comedic timing, or emotional progression. Use terms
such as reaction meme, viral clip, TikTok, Reel, GIF, or Shorts where useful. Never ask
for advice, articles, mistakes, lessons, explanations, news, or educational information.
Do not name a specific reference unless it appears in the supplied scene analysis. Do
not include site: filters and do not invent search results or URLs."""

    # Inject both external systems so automated tests remain isolated.
    def __init__(
        self,
        parallel_search: ParallelSearchClient | None = None,
        gemini_client: genai.Client | None = None,
        model_name: str | None = None,
        gemini_client_factory: Callable[[], genai.Client] = create_gemini_client,
        search_planner: SearchPlanner | None = None,
    ) -> None:
        """Initialize the agent while deferring external clients until use."""

        self._parallel_search = parallel_search or ParallelSearchClient()
        self._gemini_client = gemini_client
        self._gemini_client_factory = gemini_client_factory
        self._search_planner = search_planner or SearchPlanner(
            client=gemini_client,
            model_name=model_name,
            client_factory=gemini_client_factory,
        )
        self.model_name = model_name or os.getenv(
            "GOOGLE_GENAI_MODEL", "gemini-2.5-flash"
        )

    # Run one initial search round and at most one quality-triggered fallback round.
    def search(
        self,
        scene: Scene,
        scene_analysis: SceneAnalysis,
        preferences: ReferenceSearchPreferences,
        attempted_queries: list[str] | None = None,
        failure_diagnosis: str | None = None,
        allow_artifact_retry: bool = True,
    ) -> CulturalSearchResult:
        """Return normalized real candidates sourced exclusively from Parallel."""

        plan = self._search_planner.plan(
            scene,
            scene_analysis,
            preferences,
            attempted_queries=attempted_queries,
            failure_diagnosis=failure_diagnosis,
        )
        original_queries = plan.queries
        if not original_queries:
            return CulturalSearchResult(
                candidates=[],
                searched_queries=[],
                warnings=["This scene analysis did not contain reference queries."],
            )

        objective = self._build_scene_objective(scene, scene_analysis, preferences, plan)
        retrieval_session_id = f"icra_{uuid4().hex}"
        initial = self._parallel_search.search_cultural_references(
            queries=original_queries,
            reference_type=preferences.reference_type,
            era=preferences.era,
            match_for=preferences.match_for,
            obscurity=preferences.obscurity,
            max_results=self.RAW_CANDIDATE_LIMIT,
            objective=objective,
            session_id=retrieval_session_id,
        )
        initial_accepted, _ = filter_informational_candidates(initial.candidates)
        refined = None
        if allow_artifact_retry and (
            count_direct_artifacts(initial_accepted)
            < self.MIN_ARTIFACTS_BEFORE_REFORMULATION
        ):
            try:
                plan = self._search_planner.plan(
                    scene,
                    scene_analysis,
                    preferences,
                    attempted_queries=initial.searched_queries,
                    failure_diagnosis=(
                        "Too few direct cultural artifacts survived the first gate; "
                        "replace topic language with observable reactions and moments."
                    ),
                )
                refined_queries = plan.queries
                refined = self._parallel_search.search_cultural_references(
                    queries=refined_queries,
                    reference_type=preferences.reference_type,
                    era=preferences.era,
                    match_for=preferences.match_for,
                    obscurity=preferences.obscurity,
                    max_results=self.RAW_CANDIDATE_LIMIT,
                    objective=objective,
                    session_id=retrieval_session_id,
                )
            except Exception as exc:
                initial.warnings.append(
                    "The second artifact-search round was unavailable: "
                    f"{type(exc).__name__}."
                )

        combined_raw = deduplicate_candidates(
            [
                *initial.candidates,
                *(refined.candidates if refined is not None else []),
            ],
            limit=self.RAW_CANDIDATE_LIMIT,
        )
        accepted, _ = filter_informational_candidates(combined_raw)
        enriched, extract_warnings, extracted_count = (
            self._parallel_search.enrich_ambiguous_candidates(
                prioritize_artifacts(accepted),
                objective=objective,
                search_queries=[
                    *initial.searched_queries,
                    *(refined.searched_queries if refined is not None else []),
                ],
            )
        )
        final_candidates, _ = filter_informational_candidates(enriched)
        searched_queries = [
            *initial.searched_queries,
            *(refined.searched_queries if refined is not None else []),
        ]
        failed_queries = [
            *initial.failed_queries,
            *(refined.failed_queries if refined is not None else []),
        ]
        warnings = [
            *initial.warnings,
            *(refined.warnings if refined is not None else []),
            *extract_warnings,
        ]
        session_ids = list(
            dict.fromkeys(
                [
                    *initial.session_ids,
                    *(refined.session_ids if refined is not None else []),
                ]
            )
        )
        return CulturalSearchResult(
            candidates=prioritize_artifacts(final_candidates),
            searched_queries=searched_queries,
            failed_queries=failed_queries,
            warnings=warnings,
            session_ids=session_ids,
            raw_candidate_count=len(combined_raw),
            rejected_candidate_count=len(combined_raw) - len(final_candidates),
            extracted_candidate_count=extracted_count,
            retry_count=int(refined is not None),
            search_plan=plan,
        )

    # Ask Gemini only for improved search intent, never for source candidates.
    def _reformulate_queries(
        self,
        scene: Scene,
        scene_analysis: SceneAnalysis,
        preferences: ReferenceSearchPreferences,
        attempted_queries: list[str],
    ) -> list[str]:
        """Generate one replacement query set for weak initial retrieval."""

        prompt = (
            f"Scene heading: {scene.heading}\n"
            f"Primary beat: {scene_analysis.primary_beat}\n"
            f"Mechanism: {scene_analysis.comedic_or_dramatic_mechanism}\n"
            f"Emotions: {', '.join(scene_analysis.emotions)}\n"
            f"Visuals: {', '.join(scene_analysis.visual_characteristics)}\n"
            f"Reference type: {preferences.reference_type.value}\n"
            f"Era: {preferences.era.value}\n"
            f"Match priority: {preferences.match_for.value}\n"
            f"Attempted queries: {', '.join(attempted_queries)}"
        )
        try:
            response = self._get_gemini_client().models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=self.SYSTEM_INSTRUCTION,
                    response_mime_type="application/json",
                    response_schema=QueryReformulation,
                    safety_settings=GEMINI_SAFETY_SETTINGS,
                    temperature=0.2,
                ),
            )
            reformulation = (
                QueryReformulation.model_validate(response.parsed)
                if response.parsed is not None
                else QueryReformulation.model_validate_json(response.text)
            )
            return reformulation.queries
        except (ValidationError, ValueError, TypeError, AttributeError) as exc:
            raise CulturalSearchError(
                "Gemini returned invalid query reformulation output."
            ) from exc
        except Exception as exc:
            raise CulturalSearchError(
                f"Gemini query reformulation failed: {exc}"
            ) from exc

    # Give Parallel a complete objective while keeping keyword queries concise.
    def _build_scene_objective(
        self,
        scene: Scene,
        scene_analysis: SceneAnalysis,
        preferences: ReferenceSearchPreferences,
        plan: object | None = None,
    ) -> str:
        """Translate scene semantics and filters into a Parallel objective."""

        type_labels = {
            "all": "memes, internet culture, film, television, anime, and viral moments",
            "memes": "memes",
            "reaction_gifs": "reaction GIFs",
            "internet_culture": "internet culture",
            "film": "film moments",
            "tv": "television moments",
            "anime": "anime",
            "tiktok_short_form": "TikTok, Reels, and YouTube Shorts",
            "instagram_reels": "Instagram Reels",
        }
        obscurity_text = (
            "mainstream and widely recognizable"
            if preferences.obscurity <= 30
            else "niche, cult, or subculture-specific"
            if preferences.obscurity >= 70
            else "a balanced mix of mainstream and niche"
        )
        return (
            "Find direct public pages for visual cultural artifacts that can guide this "
            f"scene: {scene.heading}. The primary beat is {scene_analysis.primary_beat}. "
            f"The mechanism is {scene_analysis.comedic_or_dramatic_mechanism}. Prioritize "
            f"{type_labels[preferences.reference_type.value]} from {preferences.era.value}, "
            f"matched for {preferences.match_for.value}, with {obscurity_text} recognition. "
            "Return actual posts, videos, Shorts, Reels, GIFs, meme pages, or identifiable "
            "film/TV moments showing comparable performance, body language, facial reaction, "
            "blocking, visual action, or comedic timing. Exclude news, advice, business blogs, "
            "educational pages, SEO listicles, and articles merely discussing the topic. "
            f"Creative target and explicit user intent: {getattr(plan, 'creative_target', '')}. "
            f"Desired performance: {getattr(plan, 'desired_performance', '')}."
        )

    # Create Gemini only when the optional weak-result reformulation is required.
    def _get_gemini_client(self) -> genai.Client:
        """Return the configured Gemini client for query reformulation."""

        if self._gemini_client is None:
            self._gemini_client = self._gemini_client_factory()
        return self._gemini_client

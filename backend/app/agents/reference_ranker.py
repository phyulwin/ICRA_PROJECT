# backend/app/agents/reference_ranker.py
"""Gemini component assessment with deterministic application-owned ranking."""

import json
import os
from collections.abc import Callable, Sequence
from datetime import datetime, timezone

from google import genai
from google.genai import types
from pydantic import ValidationError

from backend.app.schemas.reference import (
    CulturalReferenceCandidate,
    CulturalReferenceType,
    GeminiReferenceAssessment,
    GeminiReferenceAssessmentBatch,
    MatchFor,
    RankedReference,
    ReferenceAssessment,
    ReferenceSearchPreferences,
    ReferenceType,
)
from backend.app.schemas.scene import Scene, SceneAnalysis
from backend.app.schemas.search_plan import SearchPlan
from backend.app.services.gemini_client import create_gemini_client
from backend.app.services.gemini_safety import GEMINI_SAFETY_SETTINGS
from backend.app.services.cancellation import CancellationToken
from backend.app.services.reference_quality import DIRECT_ARTIFACT_TYPES, is_blocked_source_url


# Provide a dedicated boundary for structured ranking failures.
class ReferenceRankingError(RuntimeError):
    """Raised when Gemini cannot assess real candidate references safely."""


# Own all final-score weights in application code rather than model output.
WEIGHTS_BY_PRIORITY: dict[MatchFor, dict[str, float]] = {
    MatchFor.BEST_OVERALL: {
        "situational_similarity": 0.15, "facial_expression_similarity": 0.10,
        "performance_similarity": 0.15, "body_language_similarity": 0.10,
        "visual_similarity": 0.10, "timing_similarity": 0.10,
        "emotional_similarity": 0.10, "camera_framing_similarity": 0.05,
        "recognizability": 0.10, "artifact_quality": 0.05,
    },
    MatchFor.SITUATION: {
        "situational_similarity": 0.35, "performance_similarity": 0.15,
        "timing_similarity": 0.15, "emotional_similarity": 0.10,
        "visual_similarity": 0.10, "body_language_similarity": 0.05,
        "recognizability": 0.05, "artifact_quality": 0.05,
    },
    MatchFor.PERFORMANCE: {
        "performance_similarity": 0.35, "body_language_similarity": 0.15,
        "facial_expression_similarity": 0.15, "situational_similarity": 0.10,
        "timing_similarity": 0.10, "emotional_similarity": 0.05,
        "visual_similarity": 0.05, "recognizability": 0.05,
    },
    MatchFor.FACIAL_EXPRESSION: {
        "facial_expression_similarity": 0.35, "emotional_similarity": 0.20,
        "performance_similarity": 0.15, "situational_similarity": 0.10,
        "visual_similarity": 0.10, "recognizability": 0.10,
    },
    MatchFor.VISUAL_COMPOSITION: {
        "visual_similarity": 0.35, "camera_framing_similarity": 0.25,
        "situational_similarity": 0.10, "body_language_similarity": 0.10,
        "performance_similarity": 0.05, "emotional_similarity": 0.05,
        "recognizability": 0.05, "artifact_quality": 0.05,
    },
    MatchFor.BODY_LANGUAGE: {
        "body_language_similarity": 0.35, "performance_similarity": 0.20,
        "visual_similarity": 0.15, "situational_similarity": 0.10,
        "emotional_similarity": 0.10, "recognizability": 0.05,
        "artifact_quality": 0.05,
    },
    MatchFor.COMEDIC_TIMING: {
        "timing_similarity": 0.35, "situational_similarity": 0.20,
        "performance_similarity": 0.15, "emotional_similarity": 0.10,
        "visual_similarity": 0.10, "recognizability": 0.10,
    },
    MatchFor.EMOTIONAL_BEAT: {
        "emotional_similarity": 0.35, "facial_expression_similarity": 0.20,
        "performance_similarity": 0.15, "timing_similarity": 0.10,
        "situational_similarity": 0.05, "body_language_similarity": 0.05,
        "recognizability": 0.05, "artifact_quality": 0.05,
    },
    MatchFor.CAMERA_FRAMING: {
        "camera_framing_similarity": 0.40, "visual_similarity": 0.25,
        "situational_similarity": 0.10, "body_language_similarity": 0.05,
        "performance_similarity": 0.05, "timing_similarity": 0.05,
        "recognizability": 0.05, "artifact_quality": 0.05,
    },
}


# Calculate the final score deterministically and adapt recognition to obscurity intent.
def calculate_weighted_score(
    assessment: ReferenceAssessment,
    preferences: ReferenceSearchPreferences,
) -> int:
    """Return an application-owned 0–100 weighted reference score."""

    weights = WEIGHTS_BY_PRIORITY[preferences.match_for]
    recognition_target = preferences.recognition
    recognizability_fit = max(0, 100 - abs(assessment.recognizability - recognition_target))
    components = {
        "situational_similarity": assessment.situational_similarity,
        "emotional_similarity": assessment.emotional_similarity,
        "facial_expression_similarity": assessment.facial_expression_similarity,
        "performance_similarity": assessment.performance_similarity,
        "body_language_similarity": assessment.body_language_similarity,
        "visual_similarity": assessment.visual_similarity,
        "timing_similarity": assessment.timing_similarity,
        "camera_framing_similarity": assessment.camera_framing_similarity,
        "recognizability": recognizability_fit,
        "artifact_quality": assessment.artifact_quality,
    }
    return round(
        sum(components[name] * weight for name, weight in weights.items())
    )


# Apply evidence-backed era and reference-strategy fit after component weighting.
def calculate_candidate_score(assessment: ReferenceAssessment, candidate: CulturalReferenceCandidate, preferences: ReferenceSearchPreferences) -> int:
    """Return a deterministic score without fabricating missing dates or popularity."""

    score = calculate_weighted_score(assessment, preferences)
    if preferences.reference_type != ReferenceType.ALL:
        score += 6 if _matches_reference_type(candidate, preferences.reference_type) else -18
    era_fit = _era_fit(candidate.published_at, preferences.era.value)
    if era_fit is not None:
        score += round((era_fit - 50) * 0.10)
    return max(0, min(100, score))


# Determine selected-type adherence from source and artifact facts.
def _matches_reference_type(candidate: CulturalReferenceCandidate, reference_type: ReferenceType) -> bool:
    """Return whether a classified real candidate satisfies the retrieval strategy."""

    artifact = candidate.cultural_reference_type
    platform = candidate.source_platform
    if reference_type == ReferenceType.TIKTOK_SHORT_FORM:
        return platform.value in {"tiktok", "instagram"} and artifact.value in {"tiktok", "instagram_reel", "viral_video"}
    if reference_type == ReferenceType.INSTAGRAM_REELS:
        return artifact == CulturalReferenceType.INSTAGRAM_REEL
    if reference_type == ReferenceType.MEMES:
        return artifact.value in {"reaction_meme", "gif"}
    if reference_type == ReferenceType.REACTION_GIFS:
        return artifact == CulturalReferenceType.GIF
    if reference_type == ReferenceType.ANIME:
        return artifact == CulturalReferenceType.ANIME_MOMENT
    if reference_type in {ReferenceType.FILM, ReferenceType.TV}:
        return artifact == CulturalReferenceType.FILM_TV_MOMENT
    if reference_type == ReferenceType.INTERNET_CULTURE:
        return artifact in DIRECT_ARTIFACT_TYPES
    return True


# Score only genuine provider dates and remain neutral when evidence is absent.
def _era_fit(published_at: str | None, era_value: str) -> int | None:
    """Return an evidence-backed 0-100 era fit or None for unknown dates."""

    if era_value == "any" or not published_at:
        return None
    try:
        year = datetime.fromisoformat(published_at.replace("Z", "+00:00")).year
    except (TypeError, ValueError):
        try:
            year = int(published_at[:4])
        except (TypeError, ValueError):
            return None
    current_year = datetime.now(timezone.utc).year
    ranges = {"2020_present": (2020, current_year), "2015_2019": (2015, 2019), "2010_2014": (2010, 2014), "2000s": (2000, 2009), "pre_2000": (0, 1999)}
    if era_value == "trending_current":
        return 100 if year >= current_year - 1 else 60 if year >= current_year - 3 else 0
    start, end = ranges.get(era_value, (0, current_year))
    return 100 if start <= year <= end else 0


# Derive result explanations from independent scores rather than model prose alone.
def _best_for(assessment: ReferenceAssessment) -> list[str]:
    """Return the two strongest creative dimensions."""

    values = {"Situation": assessment.situational_similarity, "Facial Expression": assessment.facial_expression_similarity, "Performance": assessment.performance_similarity, "Body Language": assessment.body_language_similarity, "Visual Composition": assessment.visual_similarity, "Comedic Timing": assessment.timing_similarity, "Emotional Beat": assessment.emotional_similarity, "Camera / Framing": assessment.camera_framing_similarity}
    return [name for name, _ in sorted(values.items(), key=lambda item: item[1], reverse=True)[:2]]


# Assess a bounded candidate set and join results back to immutable Parallel facts.
class ReferenceRanker:
    """Use Gemini for component judgments and application code for final ranking."""

    MAX_CANDIDATES_FOR_GEMINI = 10
    SYSTEM_INSTRUCTION = """You are a cultural-reference evaluator for film direction.
Evaluate only the supplied real web candidates against the supplied screenplay scene.
Use the exact candidate IDs. Score each requested component from 0 to 100. Base claims
only on the supplied title and excerpt. Never create or modify titles, URLs, sources, or
candidate IDs. Do not calculate or return an overall score. The compact response fields
map as follows: id=candidate ID, emotion=emotional similarity,
situation=situational similarity, facial=facial-expression similarity,
performance=performance similarity, body=body-language similarity,
visual=visual-composition similarity, acting=acting similarity,
timing=timing similarity, camera=camera/framing similarity,
recognition=an inferred recognizability estimate from source and cultural evidence,
culture=cultural relevance,
artifact=true only when the URL and evidence represent an actual identifiable post,
video, GIF, meme, or film/TV/anime moment; kind must be reaction_meme, viral_video,
tiktok, instagram_reel, gif, film_tv_moment, anime_moment, informational_article, or
other; quality=artifact evidence quality; evidence=the source evidence; reason=why the
observable performance, facial expression, body language, action, blocking, or timing
matches; elements lists concrete useful directing elements. An article discussing a similar topic is not an artifact, regardless of semantic
similarity, and must use informational_article with artifact=false."""

    # Accept an injected Gemini client for deterministic automated testing.
    def __init__(
        self,
        client: genai.Client | None = None,
        model_name: str | None = None,
        client_factory: Callable[[], genai.Client] = create_gemini_client,
        minimum_artifact_quality: int | None = None,
        minimum_match_score: int | None = None,
    ) -> None:
        """Initialize the ranker while deferring credentials until use."""

        self._client = client
        self._client_factory = client_factory
        self.model_name = model_name or os.getenv(
            "GOOGLE_GENAI_MODEL", "gemini-2.5-flash"
        )
        self.minimum_artifact_quality = (
            minimum_artifact_quality
            if minimum_artifact_quality is not None
            else _read_threshold("REFERENCE_MIN_ARTIFACT_QUALITY", 60)
        )
        self.minimum_match_score = (
            minimum_match_score
            if minimum_match_score is not None
            else _read_threshold("REFERENCE_MIN_MATCH_SCORE", 55)
        )

    # Send only a reduced payload, validate component scores, then rank locally.
    def rank(
        self,
        scene: Scene,
        scene_analysis: SceneAnalysis,
        candidates: Sequence[CulturalReferenceCandidate],
        preferences: ReferenceSearchPreferences,
        search_plan: SearchPlan | None = None,
        cancellation_token: CancellationToken | None = None,
    ) -> list[RankedReference]:
        """Return the top real candidates ordered by deterministic final score."""

        token = cancellation_token or CancellationToken()
        token.raise_if_cancelled()
        evidence_eligible = [
            candidate
            for candidate in candidates
            if candidate.cultural_reference_type in DIRECT_ARTIFACT_TYPES
            and not is_blocked_source_url(str(candidate.url))
        ]
        reduced_candidates = list(
            evidence_eligible[: self.MAX_CANDIDATES_FOR_GEMINI]
        )
        if not reduced_candidates:
            return []

        payload = [
            {
                "candidate_id": candidate.id,
                "title": candidate.title,
                "source_domain": candidate.source_domain,
                "snippet": candidate.snippet[:1200],
                "discovered_from_query": candidate.discovered_from_query,
                "source_platform": candidate.source_platform.value,
                "preclassified_type": candidate.cultural_reference_type.value,
                "search_family": candidate.search_family,
                "discovered_from_queries": candidate.discovered_from_queries,
                "parallel_extracted": bool(
                    candidate.source_metadata.get("parallel_extracted")
                ),
            }
            for candidate in reduced_candidates
        ]
        prompt = (
            f"SCENE\n{scene.raw_text}\n\n"
            f"PRIMARY BEAT\n{scene_analysis.primary_beat}\n\n"
            f"EMOTIONS\n{', '.join(scene_analysis.emotions)}\n\n"
            f"MECHANISM\n{scene_analysis.comedic_or_dramatic_mechanism}\n\n"
            f"MATCH PRIORITY\n{preferences.match_for.value}\n\n"
            f"SEARCH PLAN\n{search_plan.model_dump_json() if search_plan else '{}'}\n\n"
            f"CANDIDATES\n{json.dumps(payload, ensure_ascii=False)}"
        )
        try:
            response = self._get_client().models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=self.SYSTEM_INSTRUCTION,
                    response_mime_type="application/json",
                    response_schema=GeminiReferenceAssessmentBatch,
                    safety_settings=GEMINI_SAFETY_SETTINGS,
                    temperature=0.0,
                ),
            )
            token.raise_if_cancelled()
            batch = (
                GeminiReferenceAssessmentBatch.model_validate(response.parsed)
                if response.parsed is not None
                else GeminiReferenceAssessmentBatch.model_validate_json(response.text)
            )
        except (ValidationError, ValueError, TypeError, AttributeError) as exc:
            raise ReferenceRankingError(
                "Gemini returned invalid structured reference assessments."
            ) from exc
        except Exception as exc:
            raise ReferenceRankingError(
                f"Gemini reference ranking failed: {exc}"
            ) from exc

        candidates_by_id = {candidate.id: candidate for candidate in reduced_candidates}
        assessments_by_id: dict[str, ReferenceAssessment] = {}
        for wire_assessment in batch.items:
            token.raise_if_cancelled()
            try:
                assessment = self._validate_assessment(wire_assessment)
            except ValidationError:
                continue
            candidate = candidates_by_id.get(assessment.candidate_id)
            if candidate is not None:
                assessment = self._apply_direct_artifact_evidence(
                    assessment,
                    candidate,
                )
                assessment = assessment.model_copy(update={"best_for": _best_for(assessment)})
            if (
                assessment.candidate_id in candidates_by_id
                and assessment.candidate_id not in assessments_by_id
            ):
                assessments_by_id[assessment.candidate_id] = assessment

        scored = [
            RankedReference(
                reference=candidates_by_id[candidate_id],
                assessment=assessment,
                overall_score=calculate_candidate_score(assessment, candidates_by_id[candidate_id], preferences),
            )
            for candidate_id, assessment in assessments_by_id.items()
        ]
        if not scored:
            raise ReferenceRankingError(
                "Gemini did not assess any supplied Parallel candidates."
            )
        ranked = [
            item
            for item in scored
            if item.assessment.artifact_verified
            and item.assessment.cultural_reference_type
            != CulturalReferenceType.INFORMATIONAL_ARTICLE
            and item.assessment.artifact_quality >= self.minimum_artifact_quality
            and item.overall_score >= self.minimum_match_score
        ]
        ranked.sort(key=lambda item: item.overall_score, reverse=True)
        return ranked[: preferences.max_results]

    # Convert the lightweight serving response into the strict domain contract.
    @staticmethod
    def _validate_assessment(
        wire_assessment: GeminiReferenceAssessment,
    ) -> ReferenceAssessment:
        """Validate all Gemini scores and collection limits after generation."""

        return ReferenceAssessment(
            candidate_id=wire_assessment.id,
            emotional_similarity=wire_assessment.emotion,
            situational_similarity=wire_assessment.situation,
            facial_expression_similarity=wire_assessment.facial,
            performance_similarity=wire_assessment.performance,
            body_language_similarity=wire_assessment.body,
            visual_similarity=wire_assessment.visual,
            acting_similarity=wire_assessment.acting,
            timing_similarity=wire_assessment.timing,
            camera_framing_similarity=wire_assessment.camera,
            recognizability=wire_assessment.recognition,
            cultural_relevance=wire_assessment.culture,
            artifact_verified=wire_assessment.artifact,
            cultural_reference_type=wire_assessment.kind,
            artifact_quality=wire_assessment.quality,
            artifact_evidence=wire_assessment.evidence,
            match_reason=wire_assessment.reason,
            tags=wire_assessment.tags,
            useful_directing_elements=wire_assessment.elements,
            best_for=[],
            recognizability_is_inferred=True,
        )

    # Treat verified direct-media URL patterns as authoritative artifact evidence.
    @staticmethod
    def _apply_direct_artifact_evidence(
        assessment: ReferenceAssessment,
        candidate: CulturalReferenceCandidate,
    ) -> ReferenceAssessment:
        """Prevent model uncertainty from discarding a proven direct artifact page."""

        if candidate.cultural_reference_type not in DIRECT_ARTIFACT_TYPES:
            return assessment
        evidence = assessment.artifact_evidence.strip() or (
            f"Direct {candidate.source_platform.value} artifact page: {candidate.title}"
        )
        return assessment.model_copy(
            update={
                "artifact_verified": True,
                "cultural_reference_type": candidate.cultural_reference_type,
                "artifact_quality": max(70, assessment.artifact_quality),
                "artifact_evidence": evidence,
            }
        )

    # Create the existing Vertex AI Gemini client only for a non-empty candidate set.
    def _get_client(self) -> genai.Client:
        """Return the configured Gemini client, creating it when required."""

        if self._client is None:
            self._client = self._client_factory()
        return self._client


# Read operational quality thresholds without allowing invalid environment values.
def _read_threshold(name: str, default: int) -> int:
    """Return one clamped 0–100 integer configuration value."""

    try:
        return max(0, min(100, int(os.getenv(name, str(default)))))
    except (TypeError, ValueError):
        return default

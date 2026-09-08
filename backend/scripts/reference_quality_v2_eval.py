# backend/scripts/reference_quality_v2_eval.py
"""Run the ten-scene live retrieval-v2 quality and five-scene A/B evaluation."""

import json
from pathlib import Path
from urllib.parse import urlsplit

from backend.app.adk.orchestrator import ReferenceWorkflowOrchestrator
from backend.app.agents.reference_ranker import ReferenceRanker
from backend.app.agents.script_analyzer import ScriptIntelligenceAgent
from backend.app.schemas.reference import ReferenceSearchPreferences, ReferenceSearchRequest
from backend.app.schemas.scene import Scene
from backend.app.services.reference_quality import DIRECT_ARTIFACT_TYPES, build_artifact_queries
from backend.app.tools.parallel_search import ParallelSearchClient


# Define the requested semantic coverage and preference combinations.
def evaluation_cases() -> list[tuple[str, Scene, ReferenceSearchPreferences]]:
    """Return ten distinct screenplay moments with explicit retrieval intent."""

    values = [
        ("caught_lying", "JOHN denies eating cake while frosting covers his shirt. His confident smile freezes as everyone stares.", {"reference_type": "anime", "match_for": "facial_expression", "user_intent": "An exaggerated anime reaction where someone realizes they got caught lying"}),
        ("awkward_pitch", "SARA proudly pitches an absurd app. Investors stare in dead silence before she gives two thumbs up.", {"reference_type": "tiktok_short_form", "match_for": "comedic_timing", "user_intent": "Recent short-form humor with awkward silence and delayed realization", "era": "trending_current"}),
        ("physical_comedy", "MILO steps onto a skateboard, windmills his arms, and lands upright only for a shelf to collapse behind him.", {"reference_type": "memes", "match_for": "situation"}),
        ("romantic_reaction", "NIA opens the door, sees her old love holding flowers, and loses her prepared speech as relief reaches her face.", {"reference_type": "all", "match_for": "best_overall"}),
        ("angry_confrontation", "AVA advances across the kitchen while BEN retreats, her quiet accusation turning into controlled fury.", {"reference_type": "film", "match_for": "performance"}),
        ("anime_exaggeration", "KAI realizes the tiny opponent defeated him; his eyes widen and his posture collapses in impossible disbelief.", {"reference_type": "anime", "match_for": "body_language"}),
        ("deadpan_humor", "LEE watches the office printer catch fire, calmly takes one sip of coffee, and returns to typing.", {"reference_type": "tv", "match_for": "comedic_timing"}),
        ("emotional_realization", "MARA recognizes her mother's handwriting and silently understands the letter was meant for her.", {"reference_type": "film", "match_for": "emotional_beat"}),
        ("visual_reveal", "The camera clears a doorway to reveal hundreds of identical red balloons filling the silent room.", {"reference_type": "internet_culture", "match_for": "camera_framing"}),
        ("no_reference", "ELI reads quietly by a rain-streaked window, turns one page, and resumes reading.", {"reference_type": "all", "match_for": "best_overall"}),
    ]
    return [(label, Scene(scene_id=f"eval_{index:02d}", heading="INT. TEST SPACE - DAY", location="TEST SPACE", time_of_day="DAY", characters=[], raw_text=f"INT. TEST SPACE - DAY\n{text}"), ReferenceSearchPreferences.model_validate(preferences)) for index, (label, text, preferences) in enumerate(values, start=1)]


# Calculate transparent artifact-quality metrics from final source-linked results.
def quality_metrics(results: list[dict[str, object]]) -> dict[str, float]:
    """Return Precision@3/5, contamination, validity, and preference adherence."""

    displayed = [item for result in results for item in result.get("new_top", [])]
    top_three = [item for result in results for item in result.get("new_top", [])[:3]]
    top_five = [item for result in results for item in result.get("new_top", [])[:5]]
    valid = lambda item: bool(item["artifact_valid"] and item["source_valid"])
    ratio = lambda items, predicate: round(100 * sum(1 for item in items if predicate(item)) / len(items), 1) if items else 100.0
    return {"precision_at_3": ratio(top_three, valid), "precision_at_5": ratio(top_five, valid), "article_contamination_rate": ratio(displayed, lambda item: item["type"] == "informational_article"), "valid_artifact_rate": ratio(displayed, lambda item: item["artifact_valid"]), "source_url_validity": ratio(displayed, lambda item: item["source_valid"]), "preference_adherence": ratio(displayed, lambda item: item["preference_adherent"])}


# Execute real Gemini planning, Parallel retrieval, Gemini assessment, and local ranking.
def run_live_evaluation() -> dict[str, object]:
    """Return machine-readable live A/B evidence without exposing credentials."""

    analyzer = ScriptIntelligenceAgent()
    orchestrator = ReferenceWorkflowOrchestrator()
    baseline_search = ParallelSearchClient()
    ranker = ReferenceRanker()
    results: list[dict[str, object]] = []
    for index, (label, scene, preferences) in enumerate(evaluation_cases()):
        analysis = analyzer.analyze_scene(scene)
        item: dict[str, object] = {"scene": label, "opportunity": analysis.reference_opportunity.value, "preferences": preferences.model_dump(mode="json"), "old_queries": [], "old_top": [], "new_plan": None, "new_queries": [], "new_top": []}
        if analysis.reference_queries:
            if index < 5:
                old_queries = build_artifact_queries(analysis.reference_queries, preferences.reference_type)
                old_candidates = baseline_search.search_cultural_references(old_queries, preferences.reference_type, preferences.era, preferences.match_for, preferences.obscurity, 24)
                old_ranked = ranker.rank(scene, analysis, old_candidates.candidates, preferences)
                item["old_queries"] = old_queries
                item["old_top"] = [_result_row(result, preferences) for result in old_ranked]
            response = orchestrator.find_references(ReferenceSearchRequest(scene=scene, scene_analysis=analysis, preferences=preferences), explicit_search=True)
            item["new_plan"] = response.search_plan.model_dump(mode="json") if response.search_plan else None
            item["new_queries"] = response.searched_queries
            item["new_top"] = [_result_row(result, preferences) for result in response.references]
        results.append(item)
    return {"cases": results, "metrics": quality_metrics(results)}


# Normalize one ranked item for human inspection and aggregate metrics.
def _result_row(result: object, preferences: ReferenceSearchPreferences) -> dict[str, object]:
    """Return source, score, artifact, and preference evidence."""

    candidate = result.reference
    assessment = result.assessment
    source_valid = urlsplit(str(candidate.url)).scheme in {"http", "https"} and bool(urlsplit(str(candidate.url)).hostname)
    from backend.app.agents.reference_ranker import _matches_reference_type
    return {"title": candidate.title, "url": str(candidate.url), "score": result.overall_score, "platform": candidate.source_platform.value, "type": assessment.cultural_reference_type.value, "artifact_classification": candidate.cultural_reference_type.value, "artifact_valid": assessment.artifact_verified and assessment.cultural_reference_type in DIRECT_ARTIFACT_TYPES, "source_valid": source_valid, "preference_adherent": preferences.reference_type.value == "all" or _matches_reference_type(candidate, preferences.reference_type), "best_for": assessment.best_for, "useful_directing_elements": assessment.useful_directing_elements, "why": assessment.match_reason}


# Print JSON for capture in the traceability report.
if __name__ == "__main__":
    try:
        evaluation = json.dumps(run_live_evaluation(), indent=2, ensure_ascii=True)
        output_path = Path(__file__).resolve().parents[2] / "docs" / "reference_quality_v2_results.json"
        output_path.write_text(evaluation + "\n", encoding="utf-8")
        print(evaluation)
    except Exception as exc:
        print(json.dumps({"error": f"{type(exc).__name__}: {exc}"}, indent=2))
        raise

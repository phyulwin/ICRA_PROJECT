# backend/scripts/reference_quality_audit.py
"""Run paid live retrieval checks for the three reference-quality scenarios."""

import json

from backend.app.agents.culture_search import CulturalSearchAgent
from backend.app.agents.reference_ranker import ReferenceRanker
from backend.app.agents.script_analyzer import ScriptIntelligenceAgent
from backend.app.schemas.reference import ReferenceSearchPreferences, ReferenceType
from backend.app.schemas.scene import Scene


# Build the requested manual test scenes without substituting fixture results.
def build_audit_scenes() -> list[tuple[str, Scene, ReferenceSearchPreferences]]:
    """Return the caught-lie, startup-pitch, and quiet-library scenarios."""

    return [
        (
            "A_caught_lying",
            Scene(
                scene_id="scene_a",
                heading="INT. APARTMENT - NIGHT",
                location="APARTMENT",
                time_of_day="NIGHT",
                characters=["JOHN", "EMMA"],
                raw_text=(
                    "INT. APARTMENT - NIGHT\nJOHN insists he never touched the cake. "
                    "EMMA silently points to frosting smeared across his shirt. John's "
                    "confident smile freezes, and his eyes slowly drop toward the evidence."
                ),
            ),
            ReferenceSearchPreferences(
                reference_type=ReferenceType.MEMES,
                max_results=6,
            ),
        ),
        (
            "B_startup_pitch",
            Scene(
                scene_id="scene_b",
                heading="INT. CONFERENCE ROOM - DAY",
                location="CONFERENCE ROOM",
                time_of_day="DAY",
                characters=["SARAH", "INVESTORS"],
                raw_text=(
                    "INT. CONFERENCE ROOM - DAY\nSARAH beams beside a slide reading "
                    "'Uber, but for houseplants.' She delivers the absurd idea with total "
                    "conviction. The investors stare in dead silence. Sarah mistakes their "
                    "disbelief for awe and gives them two enthusiastic thumbs up."
                ),
            ),
            ReferenceSearchPreferences(
                reference_type=ReferenceType.INTERNET,
                max_results=6,
            ),
        ),
        (
            "C_quiet_library",
            Scene(
                scene_id="scene_c",
                heading="INT. LIBRARY - LATE AFTERNOON",
                location="LIBRARY",
                time_of_day="LATE AFTERNOON",
                characters=["MAYA"],
                raw_text=(
                    "INT. LIBRARY - LATE AFTERNOON\nMAYA reads alone beside a rain-streaked "
                    "window. She turns a page, pauses over a handwritten note, and quietly "
                    "closes the book. The room settles back into silence."
                ),
            ),
            ReferenceSearchPreferences(
                reference_type=ReferenceType.ALL,
                max_results=6,
            ),
        ),
    ]


# Execute the real Gemini, Parallel Search, selective Extract, and ranking pipeline.
def run_live_audit() -> list[dict[str, object]]:
    """Return concise evidence for manual inspection without printing credentials."""

    analyzer = ScriptIntelligenceAgent()
    search_agent = CulturalSearchAgent()
    ranker = ReferenceRanker()
    report: list[dict[str, object]] = []
    for label, scene, preferences in build_audit_scenes():
        analysis = analyzer.analyze_scene(scene)
        item: dict[str, object] = {
            "scene": label,
            "opportunity": analysis.reference_opportunity.value,
            "opportunity_score": analysis.reference_opportunity_score,
            "phase2_queries": analysis.reference_queries,
        }
        if not analysis.reference_queries:
            item.update({"searched_queries": [], "top_10_candidates": [], "displayed": []})
            report.append(item)
            continue

        search_result = search_agent.search(scene, analysis, preferences)
        ranked = ranker.rank(
            scene,
            analysis,
            search_result.candidates,
            preferences,
        )
        item.update(
            {
                "searched_queries": search_result.searched_queries,
                "raw_candidate_count": search_result.raw_candidate_count,
                "rejected_candidate_count": search_result.rejected_candidate_count,
                "extracted_candidate_count": search_result.extracted_candidate_count,
                "top_10_candidates": [
                    {
                        "title": candidate.title,
                        "url": str(candidate.url),
                        "platform": candidate.source_platform.value,
                        "preclassified_type": candidate.cultural_reference_type.value,
                        "extracted": bool(
                            candidate.source_metadata.get("parallel_extracted")
                        ),
                    }
                    for candidate in search_result.candidates[:10]
                ],
                "displayed": [
                    {
                        "title": result.reference.title,
                        "url": str(result.reference.url),
                        "platform": result.reference.source_platform.value,
                        "type": result.assessment.cultural_reference_type.value,
                        "artifact_quality": result.assessment.artifact_quality,
                        "match_score": result.overall_score,
                        "artifact_evidence": result.assessment.artifact_evidence,
                    }
                    for result in ranked
                ],
            }
        )
        report.append(item)
    return report


# Print machine-readable audit evidence for review and documentation.
if __name__ == "__main__":
    try:
        print(json.dumps(run_live_audit(), indent=2, ensure_ascii=True))
    except Exception as exc:
        print(json.dumps({"error": f"{type(exc).__name__}: {exc}"}, indent=2))
        raise

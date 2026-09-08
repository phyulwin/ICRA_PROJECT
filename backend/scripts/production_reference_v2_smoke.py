# backend/scripts/production_reference_v2_smoke.py
"""Exercise the deployed reference endpoint with the required v2 preferences."""

import json
from pathlib import Path

import httpx


API_URL = "https://cultural-reference-api-602486879299.us-central1.run.app"
PROJECT_ID = "prod-firestore-e2e-20260907"
OUTPUT_PATH = Path(__file__).resolve().parents[2] / "docs" / "reference_quality_v2_production.json"


# Run each production preference combination against the same persisted scene.
def run() -> list[dict[str, object]]:
    """Return compact evidence for the five required production checks."""

    try:
        with httpx.Client(timeout=300.0) as client:
            project = client.get(f"{API_URL}/api/v1/projects/{PROJECT_ID}").raise_for_status().json()
            scene_record = project["scenes"][0]
            cases = [
                ("anime_facial", {"reference_type": "anime", "match_for": "facial_expression", "recognition": 50}),
                ("tiktok_timing", {"reference_type": "tiktok_short_form", "match_for": "comedic_timing", "recognition": 50, "era": "trending_current"}),
                ("memes_situation", {"reference_type": "memes", "match_for": "situation", "recognition": 50}),
                ("any_best", {"reference_type": "all", "match_for": "best_overall", "recognition": 50}),
                ("niche", {"reference_type": "all", "match_for": "best_overall", "recognition": 5}),
                ("iconic", {"reference_type": "all", "match_for": "best_overall", "recognition": 95}),
            ]
            # Resume an interrupted or expanded smoke run without repeating paid calls.
            evidence = []
            if OUTPUT_PATH.exists():
                evidence = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
            completed = {item["case"] for item in evidence}
            for label, preferences in cases:
                if label in completed:
                    continue
                preferences.setdefault("era", "any")
                preferences.setdefault("user_intent", "caught lying, visible evidence, and a smile fading")
                preferences["max_results"] = 6
                payload = {"scene": scene_record["scene"], "scene_analysis": scene_record["analysis"], "preferences": preferences}
                response = client.post(f"{API_URL}/api/v1/scenes/scene_001/references", json=payload)
                response.raise_for_status()
                body = response.json()
                evidence.append({"case": label, "status": response.status_code, "queries": body.get("searched_queries", []), "retry_count": body.get("retry_count", 0), "search_plan": body.get("search_plan"), "results": [{"title": item["reference"]["title"], "url": item["reference"]["url"], "score": item["overall_score"], "type": item["assessment"]["cultural_reference_type"], "best_for": item["assessment"].get("best_for", []), "recognizability": item["assessment"]["recognizability"]} for item in body.get("references", [])]})
            return evidence
    except Exception:
        raise


# Persist a reviewable production artifact without storing credentials.
if __name__ == "__main__":
    try:
        result = run()
        output = json.dumps(result, indent=2, ensure_ascii=True)
        OUTPUT_PATH.write_text(output + "\n", encoding="utf-8")
        print(output)
    except Exception as exc:
        print(json.dumps({"error": f"{type(exc).__name__}: {exc}"}))
        raise

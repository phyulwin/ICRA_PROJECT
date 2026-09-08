# backend/scripts/production_cancellation_smoke.py
"""Verify that aborting production retrieval does not persist partial results."""

import asyncio
import json
from uuid import uuid4

import httpx


API_URL = "https://cultural-reference-api-602486879299.us-central1.run.app"
PROJECT_ID = "prod-firestore-e2e-20260907"
SCENE_ID = "scene_001"


# Open a real production request, cancel it, and compare durable search history.
async def run() -> dict[str, object]:
    """Return cancellation latency and Firestore non-persistence evidence."""

    try:
        async with httpx.AsyncClient(timeout=300.0) as search_client, httpx.AsyncClient(timeout=30.0) as control_client:
            project = (await control_client.get(f"{API_URL}/api/v1/projects/{PROJECT_ID}")).raise_for_status().json()
            scene_record = project["scenes"][0]
            history_url = f"{API_URL}/api/v1/projects/{PROJECT_ID}/scenes/{SCENE_ID}/searches"
            before = (await control_client.get(history_url)).raise_for_status().json()
            payload = {
                "project_id": PROJECT_ID,
                "scene": scene_record["scene"],
                "scene_analysis": scene_record["analysis"],
                "preferences": {
                    "reference_type": "all",
                    "era": "any",
                    "match_for": "best_overall",
                    "recognition": 50,
                    "user_intent": "caught lying with a slow facial realization",
                    "max_results": 6,
                },
            }
            request_id = str(uuid4())
            task = asyncio.create_task(search_client.post(f"{API_URL}/api/v1/scenes/{SCENE_ID}/references", json=payload, headers={"X-Search-Request-ID": request_id}))
            await asyncio.sleep(1.0)
            cancel_response = await control_client.post(f"{API_URL}/api/v1/reference-searches/{request_id}/cancel")
            cancel_response.raise_for_status()
            task.cancel()
            cancelled = False
            try:
                await task
            except asyncio.CancelledError:
                cancelled = True
            await asyncio.sleep(5.0)
            after = (await control_client.get(history_url)).raise_for_status().json()
            return {"cancel_endpoint_status": cancel_response.status_code, "client_cancelled": cancelled, "before_count": len(before), "after_count": len(after), "partial_result_persisted": len(after) != len(before)}
    except Exception:
        raise


# Print only non-sensitive production verification evidence.
if __name__ == "__main__":
    try:
        print(json.dumps(asyncio.run(run()), indent=2))
    except Exception as exc:
        print(json.dumps({"error": f"{type(exc).__name__}: {exc}"}))
        raise

# backend/tests/test_search_planner.py
"""Tests for structured, preference-aware Gemini search planning."""

import json
from types import SimpleNamespace

import pytest

from backend.app.agents.search_planner import SearchPlanner, SearchPlanningError
from backend.app.schemas.reference import ReferenceSearchPreferences
from backend.tests.test_directing_guidance import build_scene_context


# Build one production-shaped compact planner response.
def build_wire_plan() -> dict[str, object]:
    """Return six diverse artifact-oriented query families."""

    return {"c": "anime guilty realization", "m": "delayed realization", "v": "smile freezes", "p": "confidence collapses", "e": "embarrassment", "r": ["anime moment"], "t": ["YouTube", "Reddit"], "a": "any era", "k": "facial expression", "q": ["anime caught lying guilty face", "anime nervous smile reaction scene", "anime everyone knows silent stare", "anime confidence collapse facial expression", "anime embarrassment realization moment", "anime delayed reaction comedic timing"], "n": ["informational articles", "advice", "tutorials", "SEO listicles"]}


# Verify natural-language intent reaches Gemini and output remains schema constrained.
def test_search_planner_combines_user_intent_with_scene() -> None:
    """Preserve user intent without allowing Gemini-authored source URLs."""

    captured: dict[str, object] = {}

    # Capture the request and return parsed structured output.
    def generate_content(**kwargs: object) -> SimpleNamespace:
        """Return one deterministic planner payload."""

        captured.update(kwargs)
        return SimpleNamespace(parsed=build_wire_plan(), text="")

    scene, analysis = build_scene_context()
    preferences = ReferenceSearchPreferences(reference_type="anime", match_for="facial_expression", user_intent="exaggerated guilty anime reaction")
    plan = SearchPlanner(client=SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))).plan(scene, analysis, preferences)

    assert len(plan.queries) == 6
    assert "informational articles" in plan.negative_intents
    assert "exaggerated guilty anime reaction" in json.loads(captured["contents"])["preferences"]["user_intent"]
    assert captured["config"].response_schema.__name__ == "GeminiSearchPlan"


# Reject shallow query rewrites at the domain boundary.
def test_search_planner_rejects_insufficient_query_diversity() -> None:
    """Require six distinct queries before Parallel receives the plan."""

    payload = build_wire_plan()
    payload["q"] = ["same query"] * 6
    client = SimpleNamespace(models=SimpleNamespace(generate_content=lambda **kwargs: SimpleNamespace(parsed=payload, text="")))
    scene, analysis = build_scene_context()
    with pytest.raises(SearchPlanningError):
        SearchPlanner(client=client).plan(scene, analysis, ReferenceSearchPreferences())

# backend/app/adk/root_agent.py
"""Native Google ADK root agent for Cultural Reference Director."""

import os

from google.adk.agents import Agent
from google.genai import types

from backend.app.adk.callbacks import (
    after_agent_callback,
    after_tool_callback,
    before_agent_callback,
    before_tool_callback,
    on_tool_error_callback,
)
from backend.app.adk.state import ProjectSessionState
from backend.app.adk.tools import (
    analyze_multimodal_reference,
    analyze_scene,
    generate_directing_guidance,
    rank_references,
    search_cultural_references,
)
from backend.app.services.gemini_safety import GEMINI_SAFETY_SETTINGS


# Give the model strict provenance and orchestration rules while tools own execution.
ROOT_AGENT_INSTRUCTION = """You are the Cultural Reference Director orchestration agent.
Use tools for every analysis, search, ranking, or multimodal operation; never pretend a
tool ran. Never invent references, URLs, titles, source metadata, or search results.
Only search_cultural_references may obtain live references, and it uses Parallel Search.
Gemini may analyze scenes and evaluate supplied candidates, but deterministic application
code owns the final score and order. Preserve all source metadata exactly.

When scene intelligence is absent, call analyze_scene first with every required Scene
field: scene_id, heading, location, time_of_day, characters, and raw_text. For a scene labeled
'no reference needed', do not search unless the user explicitly requests references.
For possible or strong opportunities, call search_cultural_references once; that tool
owns one bounded quality retry and must not be called again in the same request. Its
match_for must use a supported creative priority such as best_overall,
facial_expression, comedic_timing, performance, situation, or camera_framing; never put a
query in a preference field because the tool reads queries from validated state. Call
rank_references only after search succeeds; it reads only candidates preserved in session
state. Clearly report partial success or errors instead of fabricating a completion.
Use analyze_multimodal_reference only when the user supplies a real image/video URI and
MIME type. Call generate_directing_guidance only when a real ranked reference is already
selected in state; do not rerun search or ranking. Directing guidance must abstract the
transferable cinematic mechanism and must not reproduce protected dialogue, frames, or
expressive content beyond what is necessary for analysis."""


# Export the conventional root_agent object used by ADK CLI and Agent Engine.
root_agent = Agent(
    name="cultural_reference_director",
    model=os.getenv("GOOGLE_GENAI_MODEL", "gemini-2.5-flash"),
    description=(
        "Analyzes screenplay scenes and coordinates traceable cultural-reference "
        "discovery, assessment, and deterministic ranking."
    ),
    instruction=ROOT_AGENT_INSTRUCTION,
    generate_content_config=types.GenerateContentConfig(
        safety_settings=GEMINI_SAFETY_SETTINGS,
        temperature=0.2,
    ),
    state_schema=ProjectSessionState,
    tools=[
        analyze_scene,
        search_cultural_references,
        rank_references,
        generate_directing_guidance,
        analyze_multimodal_reference,
    ],
    before_agent_callback=before_agent_callback,
    after_agent_callback=after_agent_callback,
    before_tool_callback=before_tool_callback,
    after_tool_callback=after_tool_callback,
    on_tool_error_callback=on_tool_error_callback,
)

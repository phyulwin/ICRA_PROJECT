# deployment/smoke_test_agent.py
"""Run a safe managed-session smoke test against a deployed Agent Engine."""

import asyncio
import os

import vertexai
from vertexai import agent_engines


# Require the explicit managed resource so smoke tests cannot target an assumption.
def _required_environment(name: str) -> str:
    """Return one mandatory non-empty environment setting."""

    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} must be configured before the smoke test.")
    return value


# Create a real managed session and verify the remote model invokes a tool.
async def smoke_test_agent() -> None:
    """Stream one synthetic scene-analysis request from Agent Engine."""

    try:
        project_id = _required_environment("GOOGLE_CLOUD_PROJECT")
        location = os.getenv("AGENT_ENGINE_LOCATION", "us-central1").strip()
        resource_name = _required_environment("AGENT_ENGINE_RESOURCE_NAME")
        vertexai.init(project=project_id, location=location)
        remote_agent = agent_engines.get(resource_name)
        user_id = "deployment_smoke_test"
        session = await remote_agent.async_create_session(user_id=user_id)
        session_id = session["id"] if isinstance(session, dict) else session.id
        full_search = os.getenv("AGENT_ENGINE_SMOKE_FULL_SEARCH", "False").lower() in {
            "1",
            "true",
            "yes",
        }
        message = (
            "Analyze this scene, find real cultural references, and rank them: "
            "INT. OFFICE - DAY. JOHN freezes when the upside-down slides "
            "appear and the room falls silent."
            if full_search
            else (
                "Use analyze_scene and report only the opportunity label for: "
                "INT. OFFICE - DAY. JOHN freezes when the upside-down slides "
                "appear and the room falls silent."
            )
        )
        tool_calls: list[str] = []
        errors: list[str] = []
        final_text: list[str] = []
        event_count = 0
        async for event in remote_agent.async_stream_query(
            user_id=user_id,
            session_id=session_id,
            message=message,
        ):
            event_count += 1
            if isinstance(event, dict) and event.get("errorCode"):
                errors.append(
                    f"{event.get('errorCode')}: {event.get('errorMessage', '')}"
                )
            content = event.get("content", {}) if isinstance(event, dict) else {}
            for part in content.get("parts", []):
                function_call = part.get("functionCall") or part.get("function_call")
                if function_call:
                    tool_calls.append(function_call.get("name", "unknown"))
                if part.get("text"):
                    final_text.append(part["text"])
        print(f"session_id={session_id}")
        print(f"event_count={event_count}")
        print(f"tool_calls={','.join(tool_calls)}")
        print(f"errors={' | '.join(errors)}")
        print(f"final_text={''.join(final_text)[:300]}")
        required_tools = {"analyze_scene"}
        if full_search:
            required_tools.update({"search_cultural_references", "rank_references"})
        if not required_tools.issubset(tool_calls):
            raise RuntimeError("Remote agent did not invoke the required tools.")
    except Exception:
        raise


# Provide one explicit executable validation command for deployment operators.
if __name__ == "__main__":
    asyncio.run(smoke_test_agent())

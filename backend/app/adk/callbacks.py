# backend/app/adk/callbacks.py
"""Structured, content-safe telemetry callbacks for the ADK root agent."""

from time import monotonic

from google.adk.agents.context import Context
from google.adk.tools.base_tool import BaseTool

from backend.app.services.structured_logging import configure_structured_logger, log_event


logger = configure_structured_logger("cultural_reference_director.adk")


# Log agent boundaries without recording screenplay text or model messages.
def before_agent_callback(callback_context: Context) -> None:
    """Record the start of one ADK invocation."""

    callback_context.state["temp:agent_started_at"] = monotonic()
    log_event(logger, "adk_agent_start", agent_name=callback_context.agent_name)


# Report invocation duration while leaving response content out of logs.
def after_agent_callback(callback_context: Context) -> None:
    """Record successful completion of one ADK invocation."""

    started_at = callback_context.state.get("temp:agent_started_at", monotonic())
    log_event(logger, "adk_agent_complete", agent_name=callback_context.agent_name, duration_ms=round((monotonic() - started_at) * 1000))


# Mark the start of a tool without logging potentially sensitive arguments.
def before_tool_callback(
    tool: BaseTool,
    args: dict[str, object],
    tool_context: Context,
) -> None:
    """Record one real tool invocation and its argument count."""

    tool_context.state[f"temp:tool_started:{tool.name}"] = monotonic()
    log_event(logger, "adk_tool_start", tool_name=tool.name, argument_count=len(args))


# Log safe result counts and timing after a successful tool call.
def after_tool_callback(
    tool: BaseTool,
    args: dict[str, object],
    tool_context: Context,
    tool_response: dict[str, object],
) -> None:
    """Record a completed tool invocation without response documents."""

    started_at = tool_context.state.get(
        f"temp:tool_started:{tool.name}", monotonic()
    )
    result_count = tool_response.get("result_count", 0)
    log_event(logger, "adk_tool_complete", tool_name=tool.name, duration_ms=round((monotonic() - started_at) * 1000), result_count=result_count, retry_count=tool_response.get("retry_count", 0))


# Preserve the exception boundary while reporting only its safe class name.
def on_tool_error_callback(
    tool: BaseTool,
    args: dict[str, object],
    tool_context: Context,
    error: Exception,
) -> None:
    """Record a failed tool invocation without swallowing the failure."""

    log_event(logger, "adk_tool_error", tool_name=tool.name, error_type=type(error).__name__, argument_count=len(args))

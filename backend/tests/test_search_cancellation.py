# backend/tests/test_search_cancellation.py
"""Cancellation tests for the HTTP and provider pipeline boundaries."""

import asyncio

import pytest

from backend.app.main import _run_cancellable_search
from backend.app.schemas.reference import ReferenceType
from backend.app.services.cancellation import CancellationToken, SearchCancelled
from backend.app.tools.parallel_search import ParallelSearchClient


# Simulate a browser that disconnects while the backend operation is active.
class DisconnectedRequest:
    """Expose FastAPI's client-disconnect contract for a deterministic test."""

    async def is_disconnected(self) -> bool:
        """Report an immediate client disconnect."""

        return True


# Confirm the HTTP monitor cancels work and marks the shared token.
def test_disconnect_cancels_operation() -> None:
    """Stop an active operation without converting cancellation into success."""

    token = CancellationToken()

    async def operation() -> object:
        """Remain active until the disconnect monitor cancels this task."""

        await asyncio.sleep(10)
        return object()

    async def execute() -> None:
        """Run the cancellation boundary inside one event loop."""

        with pytest.raises(SearchCancelled):
            await _run_cancellable_search(DisconnectedRequest(), operation(), token)

    asyncio.run(execute())
    assert token.cancelled is True


# Stop query fan-out after an uninterruptible provider call returns.
def test_parallel_stops_before_next_query_after_cancellation() -> None:
    """Discard a late provider response and avoid starting another query."""

    token = CancellationToken()

    class CancellingClient:
        """Cancel the request during the first simulated provider call."""

        def __init__(self) -> None:
            """Initialize provider call tracking."""

            self.calls = 0

        def search(self, **kwargs: object) -> object:
            """Mark cancellation before returning the external response."""

            self.calls += 1
            token.cancel()
            return type("Response", (), {"results": []})()

    client = CancellingClient()
    provider = ParallelSearchClient(client=client)
    with pytest.raises(SearchCancelled):
        provider.search_cultural_references(
            ["first query", "second query"],
            ReferenceType.ALL,
            cancellation_token=token,
        )
    assert client.calls == 1

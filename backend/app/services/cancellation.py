# backend/app/services/cancellation.py
"""Thread-safe cooperative cancellation primitives for long retrieval work."""

from threading import Event


# Keep user cancellation distinct from provider and application failures.
class SearchCancelled(RuntimeError):
    """Raised at a safe pipeline checkpoint after cancellation is requested."""


# Share cancellation state between the async HTTP boundary and worker threads.
class CancellationToken:
    """Provide inexpensive cancellation checkpoints across pipeline services."""

    def __init__(self) -> None:
        """Initialize a request-scoped cancellation flag."""

        self._event = Event()

    def cancel(self) -> None:
        """Mark the request as cancelled without blocking the caller."""

        self._event.set()

    def raise_if_cancelled(self) -> None:
        """Stop subsequent pipeline stages after the cancellation boundary."""

        if self._event.is_set():
            raise SearchCancelled("Reference search was cancelled.")

    @property
    def cancelled(self) -> bool:
        """Return whether cancellation has been requested."""

        return self._event.is_set()

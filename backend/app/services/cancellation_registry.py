# backend/app/services/cancellation_registry.py
"""Cross-instance cancellation state for Cloud Run reference searches."""

import os
from threading import Lock

from google.api_core.exceptions import AlreadyExists
from google.cloud import firestore


# Coordinate cancellation locally and through Firestore without exposing credentials.
class SearchCancellationRegistry:
    """Track active request IDs across Cloud Run instances."""

    def __init__(self) -> None:
        """Initialize local state and defer the Firestore client until use."""

        self._enabled = os.getenv("FIRESTORE_ENABLED", "False").lower() in {"1", "true", "yes"}
        self._project = os.getenv("GOOGLE_CLOUD_PROJECT", "").strip() or None
        self._client: firestore.Client | None = None
        self._local: dict[str, tuple[str, bool]] = {}
        self._lock = Lock()

    def start(self, request_id: str, owner_id: str) -> None:
        """Register work without erasing a cancellation that arrived first."""

        with self._lock:
            self._local.setdefault(request_id, (owner_id, False))
        if not self._enabled:
            return
        try:
            self._document(request_id).create({"owner_id": owner_id, "cancelled": False, "created_at": firestore.SERVER_TIMESTAMP})
        except AlreadyExists:
            return
        except Exception:
            return

    def cancel(self, request_id: str, owner_id: str) -> bool:
        """Publish cancellation for both the current and other service instances."""

        with self._lock:
            current = self._local.get(request_id)
            if current is not None and current[0] != owner_id:
                return False
            self._local[request_id] = (owner_id, True)
        if not self._enabled:
            return current is not None
        try:
            snapshot = self._document(request_id).get()
            if not snapshot.exists or snapshot.to_dict().get("owner_id") != owner_id:
                return False
            self._document(request_id).set({"cancelled": True, "updated_at": firestore.SERVER_TIMESTAMP}, merge=True)
            return True
        except Exception:
            return False

    def is_cancelled(self, request_id: str, owner_id: str) -> bool:
        """Return cancellation state from memory or the shared Firestore marker."""

        with self._lock:
            current = self._local.get(request_id)
            if current is not None and current == (owner_id, True):
                return True
        if not self._enabled:
            return False
        try:
            snapshot = self._document(request_id).get()
            return bool(snapshot.exists and snapshot.to_dict().get("owner_id") == owner_id and snapshot.to_dict().get("cancelled"))
        except Exception:
            return False

    def finish(self, request_id: str) -> None:
        """Remove request-scoped state after success, failure, or cancellation."""

        with self._lock:
            self._local.pop(request_id, None)
        if not self._enabled:
            return
        try:
            self._document(request_id).delete()
        except Exception:
            return

    def _document(self, request_id: str) -> object:
        """Return the private Firestore marker for one request ID."""

        if self._client is None:
            self._client = firestore.Client(project=self._project)
        return self._client.collection("_reference_search_cancellations").document(request_id)

# backend/app/services/auth_service.py
"""Firebase ID-token verification for the FastAPI trust boundary."""

from threading import Lock

import firebase_admin
from firebase_admin import auth


# Represent sanitized authentication failures without exposing token details.
class AuthenticationError(RuntimeError):
    """Raised when a Firebase ID token is absent or invalid."""


# Initialize Firebase Admin once and verify every authenticated API request.
class FirebaseAuthService:
    """Validate bearer tokens using Cloud Run Application Default Credentials."""

    def __init__(self) -> None:
        """Create a process-safe lazy initialization lock."""

        self._lock = Lock()

    def verify_bearer_token(self, authorization: str | None) -> str:
        """Return the verified Firebase UID from an Authorization header."""

        if not authorization or not authorization.startswith("Bearer "):
            raise AuthenticationError("Authentication is required.")
        token = authorization.removeprefix("Bearer ").strip()
        if not token:
            raise AuthenticationError("Authentication is required.")
        try:
            self._initialize()
            decoded = auth.verify_id_token(token, check_revoked=False)
            uid = str(decoded.get("uid", "")).strip()
            if not uid:
                raise AuthenticationError("The authentication token is invalid.")
            return uid
        except AuthenticationError:
            raise
        except Exception as exc:
            raise AuthenticationError("The authentication token is invalid or expired.") from exc

    def _initialize(self) -> None:
        """Initialize Firebase Admin with the existing Google Cloud project."""

        try:
            firebase_admin.get_app()
            return
        except ValueError:
            pass
        with self._lock:
            try:
                firebase_admin.get_app()
            except ValueError:
                firebase_admin.initialize_app()

# backend/app/services/gemini_client.py
"""Shared construction for the repository's existing Vertex AI Gemini client."""

import os

from dotenv import load_dotenv
from google import genai


# Provide a specific configuration failure for service-level error translation.
class GeminiClientConfigurationError(RuntimeError):
    """Raised when required Google Cloud Gemini settings are unavailable."""


# Preserve the working Google Cloud authentication and Vertex AI configuration.
def create_gemini_client() -> genai.Client:
    """Create a Gemini client from the repository's Google Cloud environment."""

    try:
        load_dotenv()
        project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
        if not project_id:
            raise GeminiClientConfigurationError(
                "GOOGLE_CLOUD_PROJECT is not configured."
            )
        return genai.Client(
            vertexai=True,
            project=project_id,
            location=os.getenv("GOOGLE_CLOUD_LOCATION", "global"),
        )
    except GeminiClientConfigurationError:
        raise
    except Exception as exc:
        raise GeminiClientConfigurationError(
            f"Gemini client configuration failed: {exc}"
        ) from exc

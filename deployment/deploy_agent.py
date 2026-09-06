# deployment/deploy_agent.py
"""Deploy the Cultural Reference Director ADK application to Agent Engine."""

import os
import sys
from pathlib import Path

import vertexai
from google.cloud.aiplatform_v1.types.env_var import SecretRef
from vertexai import agent_engines

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]

# Make direct script execution resolve the repository package consistently.
sys.path.insert(0, str(REPOSITORY_ROOT))

from backend.app.adk.root_agent import root_agent


# Require explicit cloud deployment values rather than assuming a local environment.
def _required_environment(name: str) -> str:
    """Return a required non-placeholder environment setting."""

    value = os.getenv(name, "").strip()
    if not value or value.startswith("your-") or "your-" in value:
        raise RuntimeError(f"{name} must be configured before deployment.")
    return value


# Exclude comments and blank lines from the Agent Engine dependency payload.
def _deployment_requirements() -> list[str]:
    """Return only installable requirement entries for the remote build."""

    try:
        lines = (REPOSITORY_ROOT / "requirements.txt").read_text(
            encoding="utf-8"
        ).splitlines()
        return [
            line.strip()
            for line in lines
            if line.strip() and not line.lstrip().startswith("#")
        ]
    except OSError as exc:
        raise RuntimeError("Unable to read deployment requirements.") from exc


# Package the native ADK app with a Secret Manager reference, never a raw API key.
def deploy_agent() -> object:
    """Create and return the remote Vertex AI Agent Engine resource."""

    try:
        project_id = _required_environment("GOOGLE_CLOUD_PROJECT")
        location = os.getenv("AGENT_ENGINE_LOCATION", "us-central1").strip()
        staging_bucket = _required_environment("AGENT_ENGINE_STAGING_BUCKET")
        service_account = _required_environment("AGENT_ENGINE_SERVICE_ACCOUNT")
        secret_id = _required_environment("PARALLEL_SECRET_ID")
        secret_version = os.getenv("PARALLEL_SECRET_VERSION", "latest").strip()

        vertexai.init(
            project=project_id,
            location=location,
            staging_bucket=staging_bucket,
        )
        app = agent_engines.AdkApp(agent=root_agent, enable_tracing=True)
        resource_name = os.getenv("AGENT_ENGINE_RESOURCE_NAME", "").strip()
        deployment_options = {
            "agent_engine": app,
            "display_name": "Cultural Reference Director",
            "description": (
                "ADK orchestration for screenplay cultural-reference direction."
            ),
            "requirements": _deployment_requirements(),
            "extra_packages": ["backend"],
            "env_vars": {
                "PARALLEL_API_KEY": SecretRef(
                    secret=secret_id,
                    version=secret_version,
                ),
                "GOOGLE_GENAI_USE_VERTEXAI": "True",
                "GOOGLE_GENAI_MODEL": os.getenv(
                    "GOOGLE_GENAI_MODEL", "gemini-2.5-flash"
                ),
            },
            "service_account": service_account,
        }
        original_directory = Path.cwd()
        try:
            os.chdir(REPOSITORY_ROOT)
            if resource_name:
                deployed_agent = agent_engines.get(resource_name)
                return deployed_agent.update(**deployment_options)
            return agent_engines.create(**deployment_options)
        finally:
            os.chdir(original_directory)
    except Exception:
        raise


# Provide a deliberate command-line deployment action with a printable resource name.
if __name__ == "__main__":
    deployed_agent = deploy_agent()
    print(deployed_agent.resource_name)

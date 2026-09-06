# backend/tests/test_api.py
"""HTTP contract tests for screenplay upload validation."""

from fastapi.testclient import TestClient

from backend.app.main import app


# Reuse one synchronous client for credential-free parsing endpoints.
client = TestClient(app)


# Confirm the public parser accepts screenplay text uploads.
def test_parse_endpoint_accepts_txt() -> None:
    """Upload a text screenplay and receive structured scene JSON."""

    response = client.post(
        "/api/v1/screenplays/parse",
        files={"file": ("scene.txt", b"EXT. STREET - DAY\n\nSAM\nWait!", "text/plain")},
    )

    assert response.status_code == 200
    assert response.json()["scenes"][0]["heading"] == "EXT. STREET - DAY"


# Confirm unsupported inputs are represented as actionable client errors.
def test_parse_endpoint_rejects_unsupported_file() -> None:
    """Reject a screenplay upload whose extension is outside the allowlist."""

    response = client.post(
        "/api/v1/screenplays/parse",
        files={"file": ("scene.docx", b"invalid", "application/octet-stream")},
    )

    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]


# Confirm the configured local frontend can call multipart backend routes in a browser.
def test_local_frontend_cors_preflight() -> None:
    """Allow the documented localhost frontend origin without using a wildcard."""

    response = client.options(
        "/api/v1/screenplays/analyze",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"

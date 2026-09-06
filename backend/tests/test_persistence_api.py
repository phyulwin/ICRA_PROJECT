"""Regression tests for project persistence API boundaries."""

from datetime import datetime, timezone

from fastapi.testclient import TestClient

import backend.app.main as main_module
from backend.app.schemas.persistence import ProjectRecord


class FakeProjectPersistence:
    """Credential-free fake for route contract tests."""

    enabled = True

    def __init__(self) -> None:
        self.project = ProjectRecord(
            project_id="project-1",
            title="Demo",
            filename="demo.fountain",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

    def list_projects(self):
        return [self.project]

    def create_project(self, request):
        return self.project

    def get_project(self, project_id):
        return {**self.project.model_dump(mode="json"), "scenes": []}

    def update_project(self, project_id, request):
        return self.project

    def delete_project(self, project_id):
        return None

    def list_searches(self, project_id, scene_id):
        return []

    def get_search(self, project_id, scene_id, search_id):
        return {"search_id": search_id}

    def update_scene_selection(self, project_id, scene_id, request):
        return {"project_id": project_id, "scenes": []}

    def add_refinement(self, project_id, scene_id, request):
        return {"project_id": project_id, "scene_id": scene_id}

    def list_refinements(self, project_id, scene_id):
        return []


def test_project_lifecycle_routes(monkeypatch):
    """Expose project history CRUD without touching Firestore."""

    monkeypatch.setattr(main_module, "project_persistence", FakeProjectPersistence())
    client = TestClient(main_module.app)

    assert client.get("/api/v1/projects").status_code == 200
    assert client.post(
        "/api/v1/projects",
        json={"project_id": "project-1", "title": "Demo", "filename": "demo.fountain"},
    ).status_code == 200
    assert client.get("/api/v1/projects/project-1").status_code == 200
    assert client.patch("/api/v1/projects/project-1", json={"title": "Renamed"}).status_code == 200
    assert client.delete("/api/v1/projects/project-1").status_code == 204


def test_search_history_and_selection_routes(monkeypatch):
    """Expose immutable search history and durable selection mutations."""

    monkeypatch.setattr(main_module, "project_persistence", FakeProjectPersistence())
    client = TestClient(main_module.app)

    assert client.get("/api/v1/projects/project-1/scenes/scene_001/searches").status_code == 200
    assert client.get("/api/v1/projects/project-1/scenes/scene_001/searches/search-1").status_code == 200
    assert client.put(
        "/api/v1/projects/project-1/scenes/scene_001/selection",
        json={"search_id": "search-1", "reference_id": "reference-1"},
    ).status_code == 200
    assert client.post(
        "/api/v1/projects/project-1/scenes/scene_001/refinements",
        json={
            "user_text": "more obscure",
            "parsed_preferences": {
                "reference_type": "all",
                "era": "any",
                "match_for": "all",
                "obscurity": 80,
                "max_results": 6,
            },
        },
    ).status_code == 200

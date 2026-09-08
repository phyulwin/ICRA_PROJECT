"""Backend-only Firestore persistence for project workflow state."""

from datetime import datetime, timezone
import os
from typing import Any
from uuid import uuid4

from google.cloud import firestore

from backend.app.schemas.persistence import (
    AnalysisPersistencePayload,
    ProjectDetail,
    ProjectCreateRequest,
    ProjectRecord,
    ProjectUpdateRequest,
    RefinementRecord,
    RefinementRequest,
    SearchDetail,
    SearchRecord,
    SelectionUpdate,
)
from backend.app.schemas.reference import RankedReference, ReferenceSearchPreferences
from backend.app.schemas.scene import AnalyzedScene


class PersistenceDisabledError(RuntimeError):
    """Raised when durable persistence was not enabled for this deployment."""


class PersistenceUnavailableError(RuntimeError):
    """Raised when Firestore cannot be reached or initialized."""


class ProjectNotFoundError(RuntimeError):
    """Raised when a requested project does not exist."""


class SceneNotFoundError(RuntimeError):
    """Raised when a requested scene does not exist."""


class FirestoreProjectService:
    """Persist product workflow records without coupling routes to Firestore calls."""

    def __init__(self, client: Any | None = None) -> None:
        self._client = client
        self._initialized = client is not None

    @property
    def enabled(self) -> bool:
        return os.getenv("FIRESTORE_ENABLED", "False").lower() in {"1", "true", "yes"}

    def _db(self) -> Any:
        if not self.enabled:
            raise PersistenceDisabledError(
                "Durable persistence is disabled. Set FIRESTORE_ENABLED=True."
            )
        if self._initialized:
            return self._client
        try:
            self._client = firestore.Client(
                project=os.getenv("GOOGLE_CLOUD_PROJECT") or None
            )
            self._initialized = True
            return self._client
        except Exception as exc:
            raise PersistenceUnavailableError(
                "Firestore could not be initialized with Application Default Credentials."
            ) from exc

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    def _project_ref(self, project_id: str) -> Any:
        return self._db().collection("projects").document(project_id)

    def save_analysis(self, payload: AnalysisPersistencePayload) -> ProjectDetail:
        now = self._now()
        project_ref = self._project_ref(payload.project_id)
        try:
            existing = project_ref.get()
        except Exception as exc:
            raise PersistenceUnavailableError(
                "Firestore could not read the project before saving analysis."
            ) from exc
        created_at = existing.to_dict().get("created_at", now) if existing.exists else now
        project = ProjectRecord(
            project_id=payload.project_id,
            title=payload.filename.rsplit(".", 1)[0],
            filename=payload.filename,
            created_at=created_at,
            updated_at=now,
            screenplay_metadata={
                "media_type": payload.screenplay_metadata.get("media_type", ""),
                "character_count": payload.character_count,
            },
            scene_count=len(payload.scenes),
        )
        batch = self._db().batch()
        batch.set(project_ref, project.model_dump(mode="json"), merge=True)
        for item in payload.scenes:
            scene_ref = project_ref.collection("scenes").document(item.scene.scene_id)
            batch.set(
                scene_ref,
                {
                    "scene_id": item.scene.scene_id,
                    "heading": item.scene.heading,
                    "raw_text": item.scene.raw_text,
                    "scene": item.scene.model_dump(mode="json"),
                    "analysis": item.analysis.model_dump(mode="json"),
                    "reference_opportunity": item.analysis.reference_opportunity.value,
                    "created_at": created_at,
                    "updated_at": now,
                },
                merge=True,
            )
        try:
            batch.commit()
        except Exception as exc:
            raise PersistenceUnavailableError("Firestore could not save screenplay analysis.") from exc
        return self.get_project(payload.project_id)

    def create_project(self, request: ProjectCreateRequest) -> ProjectRecord:
        now = self._now()
        project = ProjectRecord(
            project_id=request.project_id,
            title=request.title,
            filename=request.filename,
            created_at=now,
            updated_at=now,
            status="created",
        )
        try:
            self._project_ref(request.project_id).create(project.model_dump(mode="json"))
            return project
        except Exception as exc:
            if isinstance(exc, PersistenceDisabledError):
                raise
            raise PersistenceUnavailableError("Firestore could not create the project.") from exc

    def update_project(self, project_id: str, request: ProjectUpdateRequest) -> ProjectRecord:
        values = {key: value for key, value in request.model_dump().items() if value is not None}
        values["updated_at"] = self._now()
        try:
            reference = self._project_ref(project_id)
            if not reference.get().exists:
                raise ProjectNotFoundError(f"Project {project_id} was not found.")
            reference.update(values)
            return ProjectRecord.model_validate(reference.get().to_dict())
        except ProjectNotFoundError:
            raise
        except Exception as exc:
            if isinstance(exc, PersistenceDisabledError):
                raise
            raise PersistenceUnavailableError("Firestore could not update the project.") from exc

    def list_projects(self) -> list[ProjectRecord]:
        try:
            documents = self._db().collection("projects").order_by("updated_at", direction=firestore.Query.DESCENDING).stream()
            return [ProjectRecord.model_validate(document.to_dict()) for document in documents]
        except Exception as exc:
            if isinstance(exc, (PersistenceDisabledError, PersistenceUnavailableError)):
                raise
            raise PersistenceUnavailableError("Firestore could not list projects.") from exc

    def get_project(self, project_id: str) -> ProjectDetail:
        project_ref = self._project_ref(project_id)
        try:
            project_snapshot = project_ref.get()
            if not project_snapshot.exists:
                raise ProjectNotFoundError(f"Project {project_id} was not found.")
            project = ProjectRecord.model_validate(project_snapshot.to_dict())
            scenes = [
                AnalyzedScene.model_validate(document.to_dict())
                for document in project_ref.collection("scenes").stream()
            ]
            return ProjectDetail(**project.model_dump(), scenes=scenes)
        except ProjectNotFoundError:
            raise
        except Exception as exc:
            if isinstance(exc, PersistenceDisabledError):
                raise
            raise PersistenceUnavailableError("Firestore could not load the project.") from exc

    def update_scene_selection(
        self,
        project_id: str,
        scene_id: str,
        update: SelectionUpdate,
    ) -> ProjectDetail:
        scene_ref = self._project_ref(project_id).collection("scenes").document(scene_id)
        try:
            scene_snapshot = scene_ref.get()
            if not scene_snapshot.exists:
                raise SceneNotFoundError(f"Scene {scene_id} was not found.")
            if update.reference_id:
                if not update.search_id:
                    raise ValueError("A search_id is required when selecting a reference.")
                reference_snapshot = scene_ref.collection("searches").document(update.search_id).collection("references").document(update.reference_id).get()
                if not reference_snapshot.exists:
                    raise ValueError("The selected reference was not found in the requested search.")
            values = update.model_dump()
            values["chosen_at"] = self._now() if update.reference_id else None
            scene_ref.update(values)
            self._project_ref(project_id).update({"updated_at": self._now()})
            return self.get_project(project_id)
        except (SceneNotFoundError, PersistenceDisabledError, ValueError):
            raise
        except Exception as exc:
            raise PersistenceUnavailableError("Firestore could not update reference selection.") from exc

    def save_search(
        self,
        project_id: str,
        scene_id: str,
        preferences: ReferenceSearchPreferences,
        queries: list[str],
        references: list[RankedReference],
        raw_candidate_count: int,
        retry_count: int,
        status: str,
        failed_queries: list[dict[str, Any]],
        warnings: list[str],
        search_plan=None,
    ) -> SearchDetail:
        project_ref = self._project_ref(project_id)
        scene_ref = project_ref.collection("scenes").document(scene_id)
        search_id = uuid4().hex
        now = self._now()
        search_ref = scene_ref.collection("searches").document(search_id)
        record = SearchRecord(
            search_id=search_id,
            project_id=project_id,
            scene_id=scene_id,
            queries=queries,
            preferences=preferences,
            created_at=now,
            raw_candidate_count=raw_candidate_count,
            retained_candidate_count=len(references),
            retry_count=retry_count,
            status=status,
            failed_queries=failed_queries,
            warnings=warnings,
            search_plan=search_plan,
        )
        batch = self._db().batch()
        batch.set(search_ref, record.model_dump(mode="json"))
        for ranked in references:
            reference_ref = search_ref.collection("references").document(ranked.reference.id)
            batch.set(reference_ref, ranked.model_dump(mode="json"))
        batch.update(project_ref, {"updated_at": now, "latest_search_preferences": preferences.model_dump(mode="json")})
        try:
            batch.commit()
            return SearchDetail(**record.model_dump(), references=references)
        except Exception as exc:
            raise PersistenceUnavailableError("Firestore could not save reference search.") from exc

    def list_searches(self, project_id: str, scene_id: str) -> list[SearchRecord]:
        try:
            documents = self._project_ref(project_id).collection("scenes").document(scene_id).collection("searches").order_by("created_at", direction=firestore.Query.DESCENDING).stream()
            return [SearchRecord.model_validate(document.to_dict()) for document in documents]
        except Exception as exc:
            if isinstance(exc, PersistenceDisabledError):
                raise
            raise PersistenceUnavailableError("Firestore could not list search history.") from exc

    def get_search(self, project_id: str, scene_id: str, search_id: str) -> SearchDetail:
        try:
            search_ref = self._project_ref(project_id).collection("scenes").document(scene_id).collection("searches").document(search_id)
            snapshot = search_ref.get()
            if not snapshot.exists:
                raise ProjectNotFoundError(f"Search {search_id} was not found.")
            record = SearchRecord.model_validate(snapshot.to_dict())
            references = [RankedReference.model_validate(document.to_dict()) for document in search_ref.collection("references").stream()]
            return SearchDetail(**record.model_dump(), references=references)
        except ProjectNotFoundError:
            raise
        except Exception as exc:
            if isinstance(exc, PersistenceDisabledError):
                raise
            raise PersistenceUnavailableError("Firestore could not load search history.") from exc

    def add_refinement(self, project_id: str, scene_id: str, request: RefinementRequest) -> RefinementRecord:
        now = self._now()
        record = RefinementRecord(
            refinement_id=uuid4().hex,
            project_id=project_id,
            scene_id=scene_id,
            user_text=request.user_text,
            parsed_preferences=request.parsed_preferences,
            previous_search_id=request.previous_search_id,
            created_at=now,
        )
        try:
            self._project_ref(project_id).collection("scenes").document(scene_id).collection("refinements").document(record.refinement_id).set(record.model_dump(mode="json"))
            return record
        except Exception as exc:
            if isinstance(exc, PersistenceDisabledError):
                raise
            raise PersistenceUnavailableError("Firestore could not save refinement history.") from exc

    def list_refinements(self, project_id: str, scene_id: str) -> list[RefinementRecord]:
        try:
            documents = self._project_ref(project_id).collection("scenes").document(scene_id).collection("refinements").order_by("created_at").stream()
            return [RefinementRecord.model_validate(document.to_dict()) for document in documents]
        except Exception as exc:
            if isinstance(exc, PersistenceDisabledError):
                raise
            raise PersistenceUnavailableError("Firestore could not list refinement history.") from exc

    def delete_project(self, project_id: str) -> None:
        project_ref = self._project_ref(project_id)
        try:
            if not project_ref.get().exists:
                raise ProjectNotFoundError(f"Project {project_id} was not found.")
            for scene in project_ref.collection("scenes").stream():
                scene_ref = scene.reference
                for search in scene_ref.collection("searches").stream():
                    for reference in search.reference.collection("references").stream():
                        reference.reference.delete()
                    search.reference.delete()
                for refinement in scene_ref.collection("refinements").stream():
                    refinement.reference.delete()
                scene_ref.delete()
            project_ref.delete()
        except ProjectNotFoundError:
            raise
        except Exception as exc:
            if isinstance(exc, PersistenceDisabledError):
                raise
            raise PersistenceUnavailableError("Firestore could not delete the project.") from exc

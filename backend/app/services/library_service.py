# backend/app/services/library_service.py
"""Backend-only Firestore persistence for saved references and directing boards."""

from hashlib import sha256
import os
from typing import Any
from uuid import uuid4

from google.api_core.exceptions import AlreadyExists
from google.cloud import firestore

from backend.app.schemas.directing import DirectingGuidance, DirectingGuidanceResult
from backend.app.schemas.library import (
    DirectingGuidanceDraft,
    SaveDirectingBoardRequest,
    SaveReferenceRequest,
    SavedDirectingBoard,
    SavedReference,
)
from backend.app.schemas.reference import RankedReference
from backend.app.schemas.scene import Scene, SceneAnalysis


# Give the API stable ownership and availability error categories.
class LibraryServiceError(RuntimeError):
    """Base exception for Library persistence failures."""


class LibraryNotFoundError(LibraryServiceError):
    """Raised when a requested Library resource does not exist."""


class ReferenceOwnershipError(LibraryServiceError):
    """Raised when a reference is not owned by the requested project and scene."""


# Encapsulate all Library Firestore paths and source-ownership validation.
class LibraryService:
    """Persist references, guidance drafts, and directing boards in Firestore."""

    def __init__(self, client: Any | None = None) -> None:
        """Accept an injected client while keeping production ADC initialization lazy."""

        self._client = client

    # Create the official server Firestore client only inside the backend runtime.
    def _db(self) -> Any:
        """Return a Firestore client using Cloud Run Application Default Credentials."""

        if self._client is None:
            try:
                self._client = firestore.Client(
                    project=os.getenv("GOOGLE_CLOUD_PROJECT") or None
                )
            except Exception as exc:
                raise LibraryServiceError("Library storage is unavailable.") from exc
        return self._client

    # Deny ownerless and foreign project records before resolving nested data.
    def _assert_project_owner(self, project_id: str, owner_id: str) -> None:
        """Authorize the verified Firebase user against the project document."""

        snapshot = self._db().collection("projects").document(project_id).get()
        if not snapshot.exists or snapshot.to_dict().get("owner_id") != owner_id:
            raise LibraryNotFoundError("The project was not found.")

    # Resolve one persisted scene and its original validated analysis.
    def get_scene_context(
        self,
        project_id: str,
        scene_id: str,
        owner_id: str,
    ) -> tuple[Scene, SceneAnalysis]:
        """Return a scene only when it exists beneath the requested project."""

        try:
            self._assert_project_owner(project_id, owner_id)
            project_ref = self._db().collection("projects").document(project_id)
            snapshot = project_ref.collection("scenes").document(scene_id).get()
            if not snapshot.exists:
                raise LibraryNotFoundError("The scene was not found in this project.")
            payload = snapshot.to_dict()
            return (
                Scene.model_validate(payload["scene"]),
                SceneAnalysis.model_validate(payload["analysis"]),
            )
        except (LibraryNotFoundError, ReferenceOwnershipError):
            raise
        except Exception as exc:
            raise LibraryServiceError("Library scene validation failed.") from exc

    # Load a ranked source only from its project, scene, and immutable search path.
    def get_ranked_reference(
        self,
        project_id: str,
        scene_id: str,
        search_id: str,
        reference_id: str,
        owner_id: str,
    ) -> RankedReference:
        """Return one real persisted Parallel reference after ownership validation."""

        self.get_scene_context(project_id, scene_id, owner_id)
        try:
            search_ref = (
                self._db()
                .collection("projects")
                .document(project_id)
                .collection("scenes")
                .document(scene_id)
                .collection("searches")
                .document(search_id)
            )
            search_snapshot = search_ref.get()
            if not search_snapshot.exists:
                raise ReferenceOwnershipError(
                    "The selected reference search does not belong to this scene."
                )
            search_data = search_snapshot.to_dict()
            if (
                search_data.get("project_id") != project_id
                or search_data.get("scene_id") != scene_id
            ):
                raise ReferenceOwnershipError(
                    "The selected reference search does not belong to this project."
                )
            reference_snapshot = (
                search_ref.collection("references").document(reference_id).get()
            )
            if not reference_snapshot.exists:
                raise ReferenceOwnershipError(
                    "The selected reference was not returned for this scene."
                )
            return RankedReference.model_validate(reference_snapshot.to_dict())
        except (LibraryNotFoundError, ReferenceOwnershipError):
            raise
        except Exception as exc:
            raise LibraryServiceError("Library reference validation failed.") from exc

    # Save one deduplicated reference using only server-owned ranking evidence.
    def save_reference(
        self,
        project_id: str,
        request: SaveReferenceRequest,
        owner_id: str,
    ) -> SavedReference:
        """Create or return a project Library reference without browser-authored facts."""

        scene, _ = self.get_scene_context(project_id, request.scene_id, owner_id)
        ranked = self.get_ranked_reference(
            project_id,
            request.scene_id,
            request.search_id,
            request.reference_id,
            owner_id,
        )
        source = ranked.reference
        identity = f"{request.scene_id}|{source.id}|{source.url}"
        item_id = sha256(identity.encode("utf-8")).hexdigest()[:32]
        item_ref = (
            self._db()
            .collection("projects")
            .document(project_id)
            .collection("library_references")
            .document(item_id)
        )
        score_breakdown = {
            "emotional_similarity": ranked.assessment.emotional_similarity,
            "situational_similarity": ranked.assessment.situational_similarity,
            "visual_similarity": ranked.assessment.visual_similarity,
            "acting_similarity": ranked.assessment.acting_similarity,
            "timing_similarity": ranked.assessment.timing_similarity,
            "recognizability": ranked.assessment.recognizability,
            "cultural_relevance": ranked.assessment.cultural_relevance,
        }
        payload = {
            "id": item_id,
            "owner_id": owner_id,
            "project_id": project_id,
            "scene_id": request.scene_id,
            "scene_heading": scene.heading,
            "scene_excerpt": scene.raw_text[:500],
            "reference_id": source.id,
            "reference_title": source.title,
            "reference_url": str(source.url),
            "source_domain": source.source_domain,
            "provider": str(source.source_metadata.get("provider", "parallel")),
            "description": source.snippet,
            "overall_score": ranked.overall_score,
            "score_breakdown": score_breakdown,
            "match_reason": ranked.assessment.match_reason,
            "reference_type": ranked.assessment.cultural_reference_type.value,
            "image_url": str(source.image_url) if source.image_url else None,
            "tags": ranked.assessment.tags,
            "created_at": firestore.SERVER_TIMESTAMP,
            "updated_at": firestore.SERVER_TIMESTAMP,
        }
        try:
            item_ref.create(payload)
        except AlreadyExists:
            pass
        except Exception as exc:
            raise LibraryServiceError("The reference could not be saved.") from exc
        return self.get_reference(project_id, item_id, owner_id)

    # List only references nested beneath the requested project.
    def list_references(self, project_id: str, owner_id: str) -> list[SavedReference]:
        """Return project Library references newest first."""

        try:
            self._assert_project_owner(project_id, owner_id)
            documents = (
                self._db()
                .collection("projects")
                .document(project_id)
                .collection("library_references")
                .order_by("created_at", direction=firestore.Query.DESCENDING)
                .stream()
            )
            return [SavedReference.model_validate(item.to_dict()) for item in documents]
        except Exception as exc:
            raise LibraryServiceError("Saved references could not be loaded.") from exc

    # Resolve one Library item from the project-scoped collection.
    def get_reference(self, project_id: str, item_id: str, owner_id: str) -> SavedReference:
        """Return a saved reference or a stable not-found error."""

        try:
            self._assert_project_owner(project_id, owner_id)
            snapshot = (
                self._db()
                .collection("projects")
                .document(project_id)
                .collection("library_references")
                .document(item_id)
                .get()
            )
            if not snapshot.exists:
                raise LibraryNotFoundError("The saved reference was not found.")
            return SavedReference.model_validate(snapshot.to_dict())
        except LibraryNotFoundError:
            raise
        except Exception as exc:
            raise LibraryServiceError("The saved reference could not be loaded.") from exc

    # Delete only the exact project-owned Library reference requested by the client.
    def delete_reference(self, project_id: str, item_id: str, owner_id: str) -> None:
        """Remove one saved reference after verifying it exists."""

        self.get_reference(project_id, item_id, owner_id)
        try:
            (
                self._db()
                .collection("projects")
                .document(project_id)
                .collection("library_references")
                .document(item_id)
                .delete()
            )
        except Exception as exc:
            raise LibraryServiceError("The saved reference could not be deleted.") from exc

    # Persist generated guidance before the browser can request a Library board.
    def save_guidance_draft(
        self,
        project_id: str,
        search_id: str,
        scene: Scene,
        selected_reference: RankedReference,
        guidance: DirectingGuidance,
        owner_id: str,
    ) -> DirectingGuidanceResult:
        """Store one server-generated guidance draft with its verified source."""

        self._assert_project_owner(project_id, owner_id)
        guidance_id = uuid4().hex
        draft_ref = (
            self._db()
            .collection("projects")
            .document(project_id)
            .collection("directing_guidance")
            .document(guidance_id)
        )
        payload = {
            "id": guidance_id,
            "owner_id": owner_id,
            "project_id": project_id,
            "search_id": search_id,
            "scene_id": scene.scene_id,
            "selected_reference": selected_reference.model_dump(mode="json"),
            "directing_guidance": guidance.model_dump(mode="json"),
            "created_at": firestore.SERVER_TIMESTAMP,
            "updated_at": firestore.SERVER_TIMESTAMP,
        }
        try:
            draft_ref.create(payload)
            draft = DirectingGuidanceDraft.model_validate(draft_ref.get().to_dict())
            return DirectingGuidanceResult(
                guidance_id=draft.id,
                project_id=project_id,
                search_id=search_id,
                scene_id=scene.scene_id,
                reference_url=str(selected_reference.reference.url),
                source_domain=selected_reference.reference.source_domain,
                guidance=draft.directing_guidance,
            )
        except Exception as exc:
            raise LibraryServiceError("Directing guidance could not be saved.") from exc

    # Return the newest guidance draft for refresh-safe Directing Notes rendering.
    def get_latest_guidance(
        self,
        project_id: str,
        scene_id: str,
        owner_id: str,
    ) -> DirectingGuidanceResult:
        """Load the latest generated guidance owned by one project scene."""

        try:
            self._assert_project_owner(project_id, owner_id)
            documents = (
                self._db()
                .collection("projects")
                .document(project_id)
                .collection("directing_guidance")
                .order_by("created_at", direction=firestore.Query.DESCENDING)
                .stream()
            )
            for document in documents:
                draft = DirectingGuidanceDraft.model_validate(document.to_dict())
                if draft.scene_id == scene_id:
                    return DirectingGuidanceResult(
                        guidance_id=draft.id,
                        project_id=project_id,
                        search_id=draft.search_id,
                        scene_id=scene_id,
                        reference_url=str(draft.selected_reference.reference.url),
                        source_domain=draft.selected_reference.reference.source_domain,
                        guidance=draft.directing_guidance,
                    )
            raise LibraryNotFoundError("No directing guidance has been generated for this scene.")
        except LibraryNotFoundError:
            raise
        except Exception as exc:
            raise LibraryServiceError("Directing guidance could not be loaded.") from exc

    # Create a durable board only from a server-owned guidance draft.
    def save_directing_board(
        self,
        project_id: str,
        request: SaveDirectingBoardRequest,
        owner_id: str,
    ) -> SavedDirectingBoard:
        """Persist a directing board without trusting browser-authored guidance."""

        scene, _ = self.get_scene_context(project_id, request.scene_id, owner_id)
        try:
            draft_ref = (
                self._db()
                .collection("projects")
                .document(project_id)
                .collection("directing_guidance")
                .document(request.guidance_id)
            )
            snapshot = draft_ref.get()
            if not snapshot.exists:
                raise LibraryNotFoundError("The directing guidance draft was not found.")
            draft = DirectingGuidanceDraft.model_validate(snapshot.to_dict())
            if draft.project_id != project_id or draft.scene_id != request.scene_id:
                raise ReferenceOwnershipError("The guidance does not belong to this scene.")
            board_id = uuid4().hex
            board_ref = (
                self._db()
                .collection("projects")
                .document(project_id)
                .collection("directing_boards")
                .document(board_id)
            )
            board_ref.create(
                {
                    "id": board_id,
                    "owner_id": owner_id,
                    "project_id": project_id,
                    "scene_id": request.scene_id,
                    "scene_heading": scene.heading,
                    "selected_reference": draft.selected_reference.model_dump(mode="json"),
                    "directing_guidance": draft.directing_guidance.model_dump(mode="json"),
                    "user_title": request.user_title or f"Direction for {scene.heading}",
                    "notes": request.notes,
                    "created_at": firestore.SERVER_TIMESTAMP,
                    "updated_at": firestore.SERVER_TIMESTAMP,
                }
            )
            return self.get_directing_board(project_id, board_id, owner_id)
        except (LibraryNotFoundError, ReferenceOwnershipError):
            raise
        except Exception as exc:
            raise LibraryServiceError("The directing board could not be saved.") from exc

    # List all directing boards scoped to one project.
    def list_directing_boards(self, project_id: str, owner_id: str) -> list[SavedDirectingBoard]:
        """Return project directing boards newest first."""

        try:
            self._assert_project_owner(project_id, owner_id)
            documents = (
                self._db()
                .collection("projects")
                .document(project_id)
                .collection("directing_boards")
                .order_by("created_at", direction=firestore.Query.DESCENDING)
                .stream()
            )
            return [SavedDirectingBoard.model_validate(item.to_dict()) for item in documents]
        except Exception as exc:
            raise LibraryServiceError("Directing boards could not be loaded.") from exc

    # Load one exact project-owned board for Library detail use.
    def get_directing_board(
        self,
        project_id: str,
        board_id: str,
        owner_id: str,
    ) -> SavedDirectingBoard:
        """Return one directing board or a stable not-found error."""

        try:
            self._assert_project_owner(project_id, owner_id)
            snapshot = (
                self._db()
                .collection("projects")
                .document(project_id)
                .collection("directing_boards")
                .document(board_id)
                .get()
            )
            if not snapshot.exists:
                raise LibraryNotFoundError("The directing board was not found.")
            return SavedDirectingBoard.model_validate(snapshot.to_dict())
        except LibraryNotFoundError:
            raise
        except Exception as exc:
            raise LibraryServiceError("The directing board could not be loaded.") from exc

    # Delete only the requested board and retain its source search and guidance draft.
    def delete_directing_board(self, project_id: str, board_id: str, owner_id: str) -> None:
        """Remove one directing board after confirming project ownership."""

        self.get_directing_board(project_id, board_id, owner_id)
        try:
            (
                self._db()
                .collection("projects")
                .document(project_id)
                .collection("directing_boards")
                .document(board_id)
                .delete()
            )
        except Exception as exc:
            raise LibraryServiceError("The directing board could not be deleted.") from exc

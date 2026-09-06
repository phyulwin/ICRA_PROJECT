# Durable project persistence

## Architecture

Firestore is the durable product source of truth. FastAPI owns all Firestore access through `FirestoreProjectService`; the frontend does not receive Google credentials and no agent writes Firestore documents directly. ADK state is active orchestration context, while React state is a temporary UI cache.

Binary screenplay, image, and video uploads are never stored in Firestore. Analysis stores extracted scene text and validated structured Gemini output only.

## Firestore model

```text
projects/{project_id}
  metadata, timestamps, status, selected scene, latest preferences
  scenes/{scene_id}
    parsed scene, scene analysis, selected reference pointers
    searches/{search_id}
      immutable queries, filters, counts, retry/status metadata
      references/{reference_id}
        source facts, ranking breakdown, score, match reason
    refinements/{refinement_id}
      user text, parsed preferences, previous/resulting search IDs
```

Project listing reads only top-level documents. Project detail reads scenes. Search detail reads one search and its references. Deletion explicitly traverses references, searches, refinements, scenes, and finally the project because Firestore parent deletion does not remove subcollections.

## API routes

`GET/POST /api/v1/projects`, `GET/PATCH/DELETE /api/v1/projects/{project_id}`, search-history list/detail routes, selection `PUT`, and refinement `POST`/list routes are implemented in `backend/app/main.py`. Screenplay analysis persists scenes when a project ID is supplied; every reference search creates a new search document and returns its `search_id`.

## State boundary

The frontend sends project IDs with analysis and search requests and loads reopened projects/searches from FastAPI. Legacy localStorage helpers remain unused and are intentionally not migrated. ADK state includes lightweight project and selection pointers; active scene analysis and candidate data remain available only as required within one orchestration call.

## IAM and configuration

Set `FIRESTORE_ENABLED=True` on the backend and use Application Default Credentials. Local development uses `gcloud auth application-default login`; Cloud Run uses its service identity. Grant that runtime identity the minimum Firestore datastore read/write role required by the deployment, typically `roles/datastore.user`. Do not add service-account JSON files. The service reports HTTP 503 when persistence is enabled but Firestore cannot initialize or save.

## Verification

The backend regression suite and persistence API contract tests run with mocked services. Frontend lint and production build pass. A live Firestore smoke test was attempted with ADC and a temporary project, but Google Cloud returned `SERVICE_DISABLED` because `firestore.googleapis.com` is not enabled for the configured project; no smoke data was created. Enable it, initialize a Firestore database, and rerun the smoke flow before claiming production persistence is live-verified:

```powershell
gcloud services enable firestore.googleapis.com --project sublime-night-507622-t9
gcloud firestore databases create --location=us-central1 --project sublime-night-507622-t9
```

## Known limitations

There is no authentication layer yet, so project IDs are currently client-generated and project listing is not user-scoped. Refinement records preserve the previous search pointer; linking the resulting search can be added when a conversational refinement workflow is introduced. Legacy localStorage projects are safely ignored rather than migrated.
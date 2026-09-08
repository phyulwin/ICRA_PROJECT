# Cultural Reference Director

This repository contains the production-deployed Cultural Reference Director through Phase 5: screenplay ingestion, structured Gemini analysis, live Parallel cultural-reference discovery, deterministic ranking, native Google ADK orchestration, Agent Engine, and Cloud Run delivery.

- Frontend: Next.js, React, TypeScript
- Backend: Python, FastAPI, Pydantic
- AI: Google Gemini, Vertex AI, Google ADK
- Agent infrastructure: Vertex AI Agent Engine / Agent Runtime
- Cloud: Google Cloud Platform, Cloud Run, Cloud Storage, Firestore, Secret Manager

## Project structure

```text
ICRA_PROJECT/
├── backend/
│   ├── app/
│   │   ├── agents/script_analyzer.py
│   │   ├── agents/culture_search.py
│   │   ├── agents/reference_ranker.py
│   │   ├── adk/root_agent.py
│   │   ├── adk/tools.py
│   │   ├── adk/state.py
│   │   ├── adk/callbacks.py
│   │   ├── adk/orchestrator.py
│   │   ├── schemas/scene.py
│   │   ├── schemas/reference.py
│   │   ├── services/document_processor.py
│   │   ├── services/gemini_client.py
│   │   ├── services/multimodal_analyzer.py
│   │   ├── services/reference_service.py
│   │   ├── tools/parallel_search.py
│   │   └── main.py
│   └── tests/
├── frontend/
│   ├── app/
│   ├── package.json
│   ├── tsconfig.json
│   └── next.config.mjs
├── infra/
├── docs/
├── deployment/deploy_agent.py
├── .env.example
├── .gitignore
├── requirements.txt
├── README.md
└── .venv/
```

## LOCAL DEVELOPMENT

From the repository root, install backend dependencies once:

```powershell

python -m venv .venv
..venv\Scripts\Activate.ps1

.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Create `.env` from `.env.example` and retain the existing Google Cloud settings.

Run the backend from the repository root in terminal 1:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

Run the frontend in terminal 2:

```powershell
Set-Location frontend
Copy-Item .env.example .env.local
npm install
npm run dev
```

Open `http://localhost:3000`; the FastAPI service is available at `http://localhost:8000` and its interactive API documentation is at `http://localhost:8000/docs`.

## Python backend setup

1. Create the virtual environment from the repository root:
   ```powershell
   python -m venv .venv
   ```

2. Activate the virtual environment:
   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```

3. Install dependencies:
   ```powershell
   python -m pip install -r requirements.txt
   ```

4. Run the API:
   ```powershell
   uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
   ```

## Frontend setup

From the `frontend` folder:

```powershell
npm install
npm run dev
```

When `FIRESTORE_ENABLED=True`, project metadata, extracted scenes, structured Gemini analysis, search history, ranked references, selections, and refinements are persisted in Firestore through the backend. The frontend uses FastAPI as its source of truth; uploaded binary files and active request progress remain ephemeral. For local development without ADC, leave this setting `False` and the existing in-memory workflow remains available.

## Environment

Copy `.env.example` to `.env` and update the values for your Google Cloud project and secrets.

## Application API

- `POST /api/v1/screenplays/parse`: multipart `file` containing `.pdf`, `.txt`, or `.fountain`.
- `POST /api/v1/screenplays/analyze`: parses the uploaded `file`, analyzes every scene with Gemini, and returns validated JSON.
- `POST /api/v1/screenplays/analyze-text`: accepts JSON with `text` and optional `filename`.
- `POST /api/v1/scenes/multimodal-analyze`: accepts multipart `scene_json` and an image/video `media` file.
- `POST /api/v1/scenes/{scene_id}/references`: uses existing scene analysis, calls Parallel Search at runtime, evaluates real candidates with Gemini, and returns deterministically ranked source-linked results.

The agents use the existing `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION`, and `GOOGLE_GENAI_MODEL` configuration. `PARALLEL_API_KEY` is backend-only; browser code calls FastAPI and never contacts Parallel directly.

## Google ADK local development

The product UI remains the Next.js application. ADK CLI and ADK Web are separate developer surfaces that load the same production services and require the repository root on `PYTHONPATH`:

```powershell
$env:PYTHONPATH=(Get-Location).Path
python -m dotenv -f .env run -- adk run backend/app/adk
python -m dotenv -f .env run -- adk web backend/app --port 8001
```

The root agent conditionally calls `analyze_scene`, the Parallel-backed `search_cultural_references`, deterministic `rank_references`, and URI-based `analyze_multimodal_reference`. Typed ADK state is JSON-serializable; uploaded binary media and secrets are never placed in session state.

## Agent Engine deployment

Configure `AGENT_ENGINE_LOCATION`, `AGENT_ENGINE_STAGING_BUCKET`, `AGENT_ENGINE_SERVICE_ACCOUNT`, `PARALLEL_SECRET_ID`, and `PARALLEL_SECRET_VERSION`, then run:

```powershell
python -m dotenv -f .env run -- python deployment/deploy_agent.py
```

The deployment injects `PARALLEL_API_KEY` through a Secret Manager reference rather than packaging a local `.env` file or raw secret value.

After deployment, set `AGENT_ENGINE_RESOURCE_NAME` to the returned resource and run `python -m dotenv -f .env run -- python deployment/smoke_test_agent.py` to create a managed session and verify a remote `analyze_scene` tool call. Set `AGENT_ENGINE_SMOKE_FULL_SEARCH=True` for the separate cost-bearing smoke test that also requires live Parallel search and deterministic ranking.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests -q
```

## PRODUCTION DEPLOYMENT

The public services are:

- Frontend: `https://cultural-reference-web-602486879299.us-central1.run.app`
- Backend: `https://cultural-reference-api-602486879299.us-central1.run.app`
- Liveness/readiness: backend `/health` and `/ready`

The production flow is `Browser → Next.js Cloud Run → FastAPI Cloud Run → Agent Engine → Gemini + Parallel`. Cloud Run injects `PARALLEL_API_KEY` from Secret Manager; the browser receives only `NEXT_PUBLIC_API_BASE_URL`. The API service account has Vertex AI user, log writer, monitoring metric writer, and secret-level accessor permissions; the web runtime has no project data roles.

To repeat the deployment after setting an authenticated `gcloud` project, run:

```powershell
.\deployment\deploy_cloud_run.ps1
```

The backend permits the exact deployed web origin plus localhost, limits screenplay uploads to 20 MiB and reference media to 50 MiB, and applies a 55 MiB HTTP ceiling, a 280-second application timeout, concurrency 8, and at most three instances. See [Phase 5 production deployment and safety](docs/phase5_implementation.md) for IAM, safety settings, deployment evidence, and limitations.

## Notes

The PDF implementation uses local `pypdf` extraction for deterministic screenplay splitting and Google's native PDF `Part.from_bytes` pattern as a fallback when a valid PDF has no embedded text. See the [Phase 2 implementation audit](docs/phase2_implementation.md) for official-resource traceability, adoption decisions, and deferred technologies.

See the [Phase 3 implementation guide](docs/phase3_implementation.md) and [reference retrieval quality audit](docs/reference_retrieval_quality.md) for the live Parallel search flow, provenance boundary, scoring weights, Extract policy, and measured quality.

See the [Phase 4 implementation guide](docs/phase4_implementation.md) for ADK tool/state architecture, official Google traceability, local commands, deployment prerequisites, and operational boundaries.

The core Python dependencies, including the supported Agent Engine ADK extras, are constrained in `requirements.txt`. MCP remains deferred because the current production pipeline does not require it.

## Technical Documentation

Detailed implementation and operational instructions live in the project setup guide rather than being duplicated here:

- [Project setup](docs/PROJECT_SETUP.md): architecture, project structure, local development, environment variables, API routes, ADK, Agent Engine, testing, and deployment
- [Persistence state implementation](docs/persistence_state_implementation.md): Firestore model, source-of-truth boundaries, IAM, deletion behavior, verification status, and limitations
- [Phase 2 implementation audit](docs/phase2_implementation.md)
- [Phase 3 implementation guide](docs/phase3_implementation.md)
- [Reference retrieval quality audit](docs/reference_retrieval_quality.md)
- [Phase 4 ADK implementation guide](docs/phase4_implementation.md)
- [Phase 5 production deployment and safety](docs/phase5_implementation.md)

## Acknowledgement

ChatGPT/Codex AI was used to assist with writing and developing this project.

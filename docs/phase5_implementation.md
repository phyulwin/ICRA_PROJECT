# Phase 5: Production Deployment and Safety

## Production architecture

`Browser → Next.js on Cloud Run → FastAPI on Cloud Run → Vertex AI Agent Engine → Gemini + Parallel Search → Pydantic validation and deterministic ranking → browser`

The public frontend contains only `NEXT_PUBLIC_API_BASE_URL`. FastAPI invokes the existing managed ADK resource through `backend/app/services/agent_engine_service.py`; the gateway accepts only validated function responses and preserves the Phase 2–4 schemas and provenance controls.

## Deployed resources

- Project: `sublime-night-507622-t9`
- Region: `us-central1`
- Backend: `cultural-reference-api`, `https://cultural-reference-api-602486879299.us-central1.run.app`
- Frontend: `cultural-reference-web`, `https://cultural-reference-web-602486879299.us-central1.run.app`
- Agent Engine: `projects/602486879299/locations/us-central1/reasoningEngines/5446458885734924288`
- Secret Manager: `parallel-api-key`, production version `2`

## Identity and IAM

The backend runs as `cultural-reference-api@sublime-night-507622-t9.iam.gserviceaccount.com` with project roles `roles/aiplatform.user`, `roles/logging.logWriter`, and `roles/monitoring.metricWriter`, plus secret-level `roles/secretmanager.secretAccessor` on `parallel-api-key`. The frontend runs as `cultural-reference-web@sublime-night-507622-t9.iam.gserviceaccount.com` and has no project data roles. Neither runtime was granted Owner or Editor, and Cloud Storage was not granted because uploads remain bounded in memory.

## Secret and environment handling

Cloud Run injects `PARALLEL_API_KEY` directly from Secret Manager; no raw value appears in the image, deployment script, frontend, or checked-in configuration. `.env` remains ignored and local-only, while `.env.example` contains placeholders. `frontend/scripts/check-client-secrets.mjs` fails the production build if server-only credential markers appear in emitted static assets.

Production backend settings are `APP_ENV`, `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION`, `GOOGLE_GENAI_MODEL`, `GOOGLE_GENAI_USE_VERTEXAI`, `USE_AGENT_ENGINE`, `AGENT_ENGINE_LOCATION`, `AGENT_ENGINE_RESOURCE_NAME`, `FRONTEND_ORIGINS`, `REQUEST_TIMEOUT_SECONDS`, and `MAX_HTTP_REQUEST_BYTES`. The frontend requires only `NEXT_PUBLIC_API_BASE_URL`.

## Gemini safety policy

`backend/app/services/gemini_safety.py` defines one explicit policy for hate speech, harassment, dangerous content, and sexually explicit content, each using `BLOCK_ONLY_HIGH`. It is applied to screenplay analysis, native PDF recovery, multimodal analysis, query reformulation, candidate assessment/ranking, and the ADK root agent. This threshold blocks high-confidence unsafe material while retaining ordinary dramatic screenplay analysis.

## Input, output, and abuse controls

- Screenplays: `.pdf`, `.txt`, or `.fountain`; maximum 20 MiB; maximum 300 PDF pages; maximum 2,000,000 extracted characters.
- Multimodal media: allowlisted JPEG, PNG, WebP, MP4, QuickTime, or WebM; maximum 50 MiB.
- Global HTTP body ceiling: 55 MiB; Cloud Run timeout 300 seconds; application timeout 280 seconds; backend concurrency 8; maximum three instances.
- Empty files, malformed/encrypted PDFs, MIME mismatches, disguised PDF/text payloads, NUL-containing text, unsafe filename paths, and unsupported types are rejected.
- Gemini results are parsed through Pydantic structured schemas. Parallel source URLs use `HttpUrl`, source metadata is retained, and final ranking is deterministic application code.
- React escapes displayed text. External links use a new browsing context with `noreferrer`, which also provides opener isolation in supported browsers.

## CORS, health, logging, and errors

The production allowlist contains `http://localhost:3000` and the exact deployed frontend origin; credentials and wildcards are disabled. `/health` reports process liveness. `/ready` checks only required setting names and never calls Gemini or Parallel.

FastAPI assigns or propagates `X-Request-ID`, logs route, method, response status, and latency, and never logs request bodies or credentials. ADK callbacks log agent/tool names, duration, retry count, result count, and exception class without arguments or response content. Public upstream errors are mapped to stable sanitized messages for Agent Engine, Gemini, Parallel, ranking, extraction, timeout, and configuration failures.

## Deployment

`Dockerfile` builds FastAPI. `frontend/Dockerfile` builds Next.js standalone output. `deployment/cloudbuild.frontend.yaml` supplies the public API origin at build time, and `deployment/deploy_cloud_run.ps1` documents the repeatable two-service rollout and final CORS update. Google guidance followed: Cloud Run source deployment, dedicated service identity, and Secret Manager volume/environment integration.

## Production smoke result

On 2026-09-05, the uploaded `deployment/smoke_scene.fountain` returned one Agent Engine/Gemini scene analysis with an 85/100 strong reference opportunity and six search queries. A deployed API reference request completed with 23 real Parallel candidates and three ranked references from Tenor, Reddit, and Imgur with scores 84, 82, and 76. A separate real browser run loaded the sample, displayed its structured scene analysis, invoked reference discovery, and rendered an Imgur reference card from 23 Parallel candidates after the quality gates; the frontend, backend health/readiness, and exact-origin CORS checks all returned HTTP 200.

## Known limitations

This public hackathon demo has no end-user authentication or per-user rate limiter; cost exposure is bounded only by Cloud Run concurrency and maximum instances plus upstream quotas. Uploads and browser project state are ephemeral, no persistent corpus is present, and cold starts remain possible. The deployment uses public ingress by design and should add Cloud Armor/API Gateway or authentication before an unbounded production launch.

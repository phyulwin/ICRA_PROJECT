# Phase 4: Google ADK and Agent Engine Implementation

## Production architecture

`Browser → Next.js → FastAPI → ReferenceDiscoveryService compatibility adapter → ReferenceWorkflowOrchestrator → existing ScriptIntelligenceAgent / CulturalSearchAgent / ReferenceRanker / MultimodalAnalyzer → structured Pydantic response → frontend`

The native agent surface is:

`ADK CLI or ADK Web → root_agent → thin ADK function tools → the same production services → typed ProjectSessionState`

The Next.js product is unchanged. ADK Web on port 8001 is a developer debugging surface and does not replace the application UI.

## Official Google traceability

| Official resource | Adopted pattern | Implementation | Adaptation and exclusions |
|---|---|---|---|
| [Agent Engine introduction notebook](https://github.com/GoogleCloudPlatform/generative-ai/blob/main/gemini/agent-engine/intro_agent_engine.ipynb) | Wrap an agent application for managed execution and tracing | `deployment/deploy_agent.py` | Uses the repository package and explicit production dependencies; notebook display/setup boilerplate is excluded. |
| [Deploy an ADK agent on Agent Engine](https://github.com/GoogleCloudPlatform/generative-ai/blob/main/agents/agent_engine/tutorial_deploy_your_first_adk_agent_on_agent_engine.ipynb) | `Agent` root object, plain Python function tools, `AdkApp`, staging package, remote sessions | `backend/app/adk/root_agent.py`, `backend/app/adk/tools.py`, `deployment/deploy_agent.py` | Existing business services remain authoritative; the sample weather tool and tutorial-only setup are excluded. |
| [Function calling introduction](https://github.com/GoogleCloudPlatform/generative-ai/blob/main/gemini/function-calling/intro_function_calling.ipynb) | Clear function names, typed arguments, descriptions, and application execution | `backend/app/adk/tools.py` | Tools return validated dictionaries and never claim execution without invoking the service. |
| [Forced function calling](https://github.com/GoogleCloudPlatform/generative-ai/blob/main/gemini/function-calling/forced_function_calling.ipynb) | Use forced calls only for invariants | `backend/app/adk/root_agent.py`, `backend/app/adk/orchestrator.py` | Model-level forced mode is not applied globally because no-reference and multimodal branches are conditional; the HTTP workflow enforces mandatory Parallel retrieval deterministically. |
| [Multimodal function calling](https://github.com/GoogleCloudPlatform/generative-ai/blob/main/gemini/function-calling/multimodal_function_calling.ipynb) | Combine text and media with a callable tool boundary | `backend/app/adk/tools.py`, `backend/app/services/multimodal_analyzer.py` | The ADK tool accepts a Gemini-accessible URI and MIME type so binary media does not enter conversational state. |
| [ADK state documentation](https://google.github.io/adk-docs/sessions/state/) | Session state as serializable key/value data | `backend/app/adk/state.py` | Pydantic models validate the domain state before values are committed. |
| [ADK callbacks documentation](https://google.github.io/adk-docs/callbacks/) | Before/after/error callbacks for lifecycle observability | `backend/app/adk/callbacks.py` | Logs counts, duration, retry count, and error class only; screenplay text, response bodies, and secrets are excluded. |
| [Agent Engine deployment documentation](https://cloud.google.com/vertex-ai/generative-ai/docs/agent-engine/deploy) | Secret Manager references, staging configuration, dedicated service account | `deployment/deploy_agent.py`, `.env.example` | `PARALLEL_API_KEY` is referenced by secret ID/version and is never a plain deployment setting. |

## Agent responsibilities and tool boundaries

- `analyze_scene`: validates a complete `Scene`, invokes the existing schema-constrained Gemini analyzer, and stores `SceneAnalysis`.
- `search_cultural_references`: reads validated scene state and invokes `CulturalSearchAgent`; only its existing Parallel client can produce candidates. The service owns one initial round and at most one Gemini-reformulated retry.
- `rank_references`: refuses to run without candidates in state, asks Gemini only for component assessments, and retains application-owned deterministic scoring and ordering.
- `analyze_multimodal_reference`: analyzes an image/video URI with the existing Gemini `Part` implementation; no transcription is added.
- No directing-guidance tool was added because no production directing-guidance service currently exists.

The root instruction prohibits invented references, modified provenance, repeated search calls, ranking before successful search, and claims that a tool ran when it did not. It also directs abstract filmmaking guidance to reduce unnecessary reproduction of protected material.

## Typed state

`ProjectSessionState` contains project ID, screenplay metadata, selected scene ID, scene, scene analysis, search preferences, search queries, bounded search history, raw candidates, ranked references, selected reference, directing notes, retry count, and last tool status. All stored values serialize to JSON for local in-memory/browser sessions and Agent Engine managed sessions; uploaded bytes and credentials remain outside state.

## Retry and control policy

No-reference scenes skip search by default. A user may explicitly request reference discovery through the existing FastAPI route; suitable scenes proceed through Parallel search, at most one quality-triggered reformulation round, then Gemini assessment and deterministic ranking. The root instruction permits one call to the search tool because retry ownership remains inside the existing tested `CulturalSearchAgent`, preventing an unbounded model-driven loop.

## Local operation

From the repository root:

```powershell
$env:PYTHONPATH=(Get-Location).Path
python -m dotenv -f .env run -- adk run backend/app/adk
python -m dotenv -f .env run -- adk web backend/app --port 8001
```

ADK Web is unauthenticated development software and should remain bound to localhost.

## Managed deployment

Required settings are documented in `.env.example`. `AGENT_ENGINE_LOCATION` must be a supported regional location and is intentionally separate from the existing Gemini `global` location. The deploy script packages `backend`, enables ADK tracing, installs production requirements, selects a dedicated service account, and injects the Parallel key through `SecretRef`. Supplying `AGENT_ENGINE_RESOURCE_NAME` updates that resource; omitting it creates a new resource.

`backend/__init__.py` makes the backend an explicit Python package, and the deploy script stages the relative `backend` directory from the repository root so Agent Engine unpacks an importable package without including `.env` or unrelated files.

## Explicitly deferred capabilities

- Voice and Live API: DEFER; the product currently processes uploaded documents and references.
- SQL, MCP, and Maps tools: NOT RELEVANT; current orchestration has no database or geospatial requirement.
- BigQuery, Vertex AI Search, and RAG: DEFER; there is no persistent searchable cultural corpus.
- Firestore-backed ADK sessions: DEFER; Agent Engine managed sessions and local in-memory sessions satisfy current state needs.

## Validation gates

Automated tests cover actual ADK `FunctionTool` execution, typed state updates, default no-search behavior, search-before-rank ordering, immutable Parallel source metadata, existing bounded search behavior, schemas, API contracts, ingestion, multimodal analysis, and deterministic ranking. Live local validation must show a Gemini function-call event followed by the tool response; remote validation must create a managed session and stream at least one query after deployment.

## Deployment validation record

On 2026-09-05, deployment succeeded in `us-central1` as `projects/602486879299/locations/us-central1/reasoningEngines/5446458885734924288`. A managed scene-only session streamed four events and invoked `analyze_scene`. A second managed session streamed eight events and invoked `analyze_scene → search_cultural_references → rank_references` with no errors, validating runtime access to the Secret Manager-backed Parallel credential; no candidate cleared the configured quality gates for that synthetic scene, so the final ranked collection was correctly empty.

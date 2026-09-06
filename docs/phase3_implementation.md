# Phase 3 implementation

## Runtime architecture

`Next.js scene workspace → FastAPI reference endpoint → CulturalSearchAgent → Parallel Search → ReferenceRanker with Gemini → deterministic Python scoring → source-linked frontend cards`

Parallel Search is called at runtime by `backend/app/tools/parallel_search.py` through the official `parallel-web` Python SDK. The `PARALLEL_API_KEY` exists only in the backend environment and is never sent to or referenced by browser code.

## Division of responsibility

| Component | Responsibility |
|---|---|
| Phase 2 Gemini analysis | Generates visual-artifact `reference_queries`, scene tone, emotions, visual characteristics, and performance intent |
| Parallel Search | Retrieves live web pages, titles, URLs, excerpts, publication dates, search IDs, and session IDs |
| Gemini reference ranker | Evaluates only supplied real candidates and returns component scores plus a match explanation |
| Application code | Deduplicates candidates, preserves source provenance, calculates weighted overall scores, sorts, and limits output |
| Next.js frontend | Collects preferences, calls FastAPI, displays progress, source-linked cards, score breakdowns, and scene context |

Gemini never supplies candidate titles, URLs, domains, publication dates, or final percentages. Test fakes are confined to automated tests; production candidates originate only from Parallel responses.

## Official Parallel implementation

The adapter follows the [Parallel Search API quickstart](https://docs.parallel.ai/search/search-quickstart) and uses `Parallel.search(objective=..., search_queries=...)`. Each existing Gemini query is searched independently in `fast` mode with `advanced_settings.max_results`, a bounded excerpt budget, official SDK timeout handling, and built-in retries.

The official guidance recommends concise keyword queries and a self-contained objective. The adapter caps individual queries at six words, runs broad and dedicated source-targeted searches, and moves scene context, reference type, era, match priority, and obscurity intent into the objective.

## Discovery strategy

1. Consume existing Phase 2 artifact-oriented `reference_queries` without rerunning scene analysis.
2. Run up to three broad searches plus two platform-targeted searches through Parallel in one shared session.
3. Collect up to 24 candidates, normalize factual metadata, classify URL provenance, deduplicate, and reject obvious articles or collection pages.
4. If fewer than three direct artifacts survive, allow one schema-constrained Gemini reformulation and a second, final search round.
5. Selectively call Parallel Extract for up to four promising ambiguous or sparse pages.
6. Send at most ten recognized direct artifacts with bounded excerpts to Gemini for component assessment.
7. Apply artifact-quality and match-score gates, then return at most the requested three to six candidates without padding.

## Data and source traceability

Raw `CulturalReferenceCandidate` fields remain separate from `ReferenceAssessment`. Every displayed reference requires a valid HTTP or HTTPS source URL, and its metadata records `provider=parallel`, Parallel search/session IDs, provider result position, and excerpt count.

Parallel Search currently provides no image field, so the backend resolves previews only after a reference passes every quality gate. YouTube thumbnails use the video identifier; other approved direct-artifact platforms use bounded, redirect-validated Open Graph/Twitter metadata reads. The frontend retains a neutral placeholder when no trustworthy source image is available and never assigns stock or random imagery to a real result.

## Deterministic ranking

Gemini scores emotional, situational, visual, acting, timing, recognizability, and cultural relevance from 0–100. Python calculates the overall percentage with these default weights:

The Gemini request uses a compact Pydantic wire schema without nested numeric or array bounds, following Vertex AI's supported structured-output subset. The response is immediately converted into the stricter `ReferenceAssessment` domain model, where every score must be 0–100 and tags remain bounded; invalid assessments never enter ranking.

| Component | Weight |
|---|---:|
| Visual/action | 25% |
| Situation | 20% |
| Acting/performance | 20% |
| Timing | 15% |
| Emotion | 10% |
| Recognizability | 10% |

The selected `match_for` dimension receives greater weight through predefined application constants. For niche searches, the recognizability contribution is progressively inverted while the raw Gemini recognizability score remains visible in the score breakdown.

## API contract

`POST /api/v1/scenes/{scene_id}/references`

The request sends the existing `Scene`, existing `SceneAnalysis`, and `ReferenceSearchPreferences`. This is required because Phase 2 project state currently resides in browser local storage; the backend validates the path identity and does not duplicate the Phase 2 Gemini analysis.

Supported preferences are:

- Reference type: all, memes, internet, film, anime, TikTok
- Era: any, 2000s, 2010s, 2020s, current
- Match for: all, acting, situation, visual, timing
- Obscurity: 0 mainstream through 100 niche
- Returned references: three through six

## Failure handling

- Missing `PARALLEL_API_KEY`: HTTP 503 with an actionable backend configuration message.
- Rejected credentials or other provider error: sanitized HTTP 502 response.
- Rate limiting: HTTP 429 after official SDK retries are exhausted.
- Timeout or connection failure: HTTP 504 after retries are exhausted.
- One query failure: successful results continue with `partial_success=true` and query-level diagnostics.
- Empty results: a successful empty response is returned without invoking Gemini ranking.
- Malformed Parallel result: the item is skipped and a warning is retained.
- Gemini ranker failure: HTTP 502 without fabricated or unranked results.

## Extract API decision

The [Parallel Extract API](https://docs.parallel.ai/extract/extract-quickstart) is called only for up to four promising ambiguous or sparse shortlisted pages and reuses the search session identifier. Extract enriches evidence but cannot promote an article or collection page into Top Results; display eligibility still requires a recognized direct-artifact URL.

## Configuration

```text
PARALLEL_API_KEY=your-server-side-key
REFERENCE_MIN_ARTIFACT_QUALITY=60
REFERENCE_MIN_MATCH_SCORE=55
```

Keep this variable in the FastAPI or Cloud Run environment. Never prefix it with `NEXT_PUBLIC_`.

## Live integration validation

On 2026-09-05, the full Gemini → Parallel Search → selective Extract → Gemini ranking workflow was tested against caught-lying, absurd-startup-pitch, and quiet-library scenes. See [reference retrieval quality](reference_retrieval_quality.md) for before/after queries, inspected results, measured precision, and remaining recall debt.

The validation also exposed and corrected a local configuration issue: an example `GOOGLE_APPLICATION_CREDENTIALS` path had overridden working Application Default Credentials. The environment template now leaves that variable commented unless a real service-account file is supplied.

## Phase boundary

Phase 3 does not add BigQuery, Vertex Search, Firestore production persistence, authentication, payments, Lyria, TTS, podcast generation, or Google Search. Directing Guidance remains the Phase 4 action after a user selects a reference.

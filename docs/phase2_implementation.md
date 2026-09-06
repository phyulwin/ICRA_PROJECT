# Phase 2 implementation audit

Audit date: 2026-09-04

## Executive decision

Phase 2 retains deterministic local text extraction and screenplay-specific scene parsing for ordinary PDFs, TXT, and Fountain files. Gemini native PDF handling is used only when a valid PDF has no embedded text layer; this avoids an unnecessary model call for normal screenplays while supporting scanned or image-based documents.

## Real production pipeline

`Browser upload → Next.js uploadScreenplay() → FastAPI /api/v1/screenplays/analyze → DocumentProcessor → ScriptIntelligenceAgent → Gemini on Vertex AI → Pydantic SceneAnalysis validation → Next.js scene views`

The sample screenplay button creates a real browser `File` and sends it through the same FastAPI endpoint. Production application code contains no hardcoded Gemini response and no mock screenplay analysis; deterministic fake clients exist only in backend unit tests.

## Official-resource traceability

| Official resource | Concept or code pattern reused | Implementation file | Why it was adapted | Intentionally not used |
|---|---|---|---|---|
| [Google Document Processing notebook](https://github.com/GoogleCloudPlatform/generative-ai/blob/main/gemini/use-cases/document-processing/document_processing.ipynb) | `google.genai.Client`, PDF `Part.from_bytes`, explicit `application/pdf`, `GenerateContentConfig`, Pydantic `response_schema`, `application/json`, and `response.parsed` | `backend/app/services/gemini_client.py`, `backend/app/services/document_processor.py`, `backend/app/agents/script_analyzer.py`, `backend/app/schemas/scene.py` | Native PDF input is a fallback for PDFs without a text layer; ordinary screenplay parsing remains deterministic and lower-cost | Notebook setup cells, display helpers, invoice/pay-slip schemas, document classification, Q&A, summarization, translation, comparison, table-to-HTML rendering, and manual JSON/demo output handling |
| [Google Intro Multimodal Use Cases notebook](https://github.com/GoogleCloudPlatform/generative-ai/blob/main/gemini/use-cases/intro_multimodal_use_cases.ipynb) | Ordered text-plus-media contents, `Part.from_bytes` for uploaded media, `Part`/`FileData` for `gs://` or HTTPS media, explicit MIME types, and static/agentic video processing | `backend/app/services/multimodal_analyzer.py`, `backend/app/schemas/scene.py` | One reusable service handles scene text plus an inline upload or a Gemini-accessible URI and returns filmmaking-specific structured output | Weather, audio, repository analysis, cached-content demos, UI display code, unrelated prompts, and free-form Markdown responses |

## Document-processing audit

### Patterns already present before this audit

- The backend used the official Google Gen AI SDK with the working Vertex AI project and location configuration.
- Scene analysis already used Pydantic as `response_schema`, `response_mime_type="application/json"`, and `response.parsed` before defensive Pydantic validation.
- File types and MIME types were allowlisted, file size was bounded, and PDF/TXT/Fountain extraction fed a custom screenplay scene parser.
- Multimodal uploads already used ordered scene text plus `Part.from_bytes` with an explicit image/video MIME type.

### Patterns adopted during this audit

- A valid PDF with no embedded text now falls back to Gemini native PDF understanding through `Part.from_bytes(..., mime_type="application/pdf")`.
- Native PDF transcription is schema-constrained with `ExtractedDocumentText`; it does not strip Markdown fences or parse uncontrolled JSON.
- PDF signatures are checked before parsing, supplementing extension-based validation.
- Shared Gemini client construction now has one source of truth without changing the existing Vertex AI integration.
- Multimodal analysis now also accepts `gs://` and HTTPS media using `FileData`; video can select the sample's `static` or `agentic` processing mode.

### Why local PDF extraction remains primary

For a text-based screenplay, `pypdf` is deterministic, avoids model cost and latency, and retains text needed by the screenplay-specific heading parser. Sending every PDF to Gemini first would make basic ingestion probabilistic and would not improve the normal case; native Gemini document understanding is operationally superior only as the fallback for image-based or otherwise non-extractable PDFs.

## Structured-output controls

`SceneAnalysis`, `ExtractedDocumentText`, and `MultimodalAnalysis` are Pydantic response schemas passed directly to Gemini. The SDK's parsed response is validated again with Pydantic; the text fallback uses `model_validate_json` and never removes code fences, applies regex to JSON, or accepts an unchecked dictionary.

The `SceneAnalysis` validator enforces a 0–100 opportunity score, label-to-score consistency, zero queries for “no reference needed,” and three to six queries for possible or strong opportunities.

## Technology disposition

- **BigQuery RAG — DEFER:** add it only if a durable, queryable cultural-reference corpus becomes a product requirement.
- **Vertex AI Search/Data Stores — DEFER:** add it only when Phase 3 needs managed retrieval over a persistent indexed corpus.
- **Video transcription — NOT RELEVANT:** Phase 2 analyzes filmmaking characteristics and explicitly does not require dialogue transcription.
- **Video captioning — DEFER:** consider it only if future reference indexing requires searchable asset descriptions.
- **Imagen — NOT RELEVANT:** Phase 2 analyzes source material and does not generate images.
- **Lyria — NOT RELEVANT:** music generation is outside the screenplay-analysis and reference-discovery pipeline.
- **Gemini TTS — NOT RELEVANT:** speech synthesis is outside the current product workflow.
- **Podcast generation — NOT RELEVANT:** no Phase 2 capability produces podcast content.
- **Dialogue sentiment analysis — DEFER:** current structured tone and emotion fields cover the acceptance criteria without a separate sentiment subsystem.

## Operational boundaries and technical debt

- Native PDF fallback requires the same Google Cloud credentials and Gemini model access already used by scene analysis.
- Very long scanned screenplays can exceed a model's output token limit; production hardening should add page batching and result reassembly if this becomes common.
- Inline uploaded video remains capped at 50 MB; larger assets should use the URI method backed by Cloud Storage.
- Scene analysis is currently sequential, which preserves order and predictable quota usage but may be optimized with bounded concurrency after production quota limits are established.
- Browser results are stored in local storage rather than a durable project database; persistence belongs to a later product phase.

## Phase boundary

Phase 2 prepares `reference_queries` but performs no internet search, Parallel call, reference ranking, or reference-result fabrication. BigQuery RAG and Vertex AI Search remain deferred until there is a justified persistent knowledge corpus.

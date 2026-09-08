# Reference Retrieval Quality v2

## Production architecture

The deployed path remains Browser → Next.js → FastAPI → Vertex AI Agent Engine → Gemini search planning → Parallel retrieval → Gemini artifact assessment → deterministic Python ranking → Firestore persistence → frontend. No mock responses or hardcoded ranked references participate in this path.

## What changed

Gemini now converts scene analysis, structured preferences, and optional natural-language intent into a validated `SearchPlan`. The plan records creative target, mechanism, desired action/performance/emotional beat, reference and platform targets, era, ranking priority, 6–12 diverse queries, negative intents, and any retry diagnosis.

Parallel receives bounded multi-query searches. Every candidate retains query provenance and a query-family label; canonical URL/title deduplication merges provenance instead of discarding it. Stage A rejects articles, topic pages, invalid URLs, and unverifiable artifacts before Stage B evaluates creative usefulness.

Gemini independently assesses situation, facial expression, performance, body language, visual composition, comedic timing, emotional beat, camera/framing, recognizability, and artifact quality. Pydantic structured output is used; no fence stripping, regex JSON extraction, or free-form parsing is used.

## Deterministic ranking

Gemini supplies evidence-backed assessments, but application code owns the final score. The score combines the dimensions above, artifact quality, requested-type fit, evidence-backed era fit, and distance from the requested Recognition target. Missing publication dates remain unknown and are not invented.

Facial Expression weights facial expression 35%, emotion 20%, performance 15%, situation 10%, visual 10%, and recognition 10%. Comedic Timing weights timing 35%, situation 20%, performance 15%, emotion 10%, visual 10%, and recognition 10%. Other priorities use explicit tables in `backend/app/agents/reference_ranker.py`.

When fewer than three artifacts survive, the system performs exactly one diagnosed reformulation. Attempted queries are supplied to Gemini, candidates are merged and deduplicated, and the final response exposes the retry count and diagnosis.

## Live ten-scene evaluation

On 2026-09-07, `backend/scripts/reference_quality_v2_eval.py` exercised caught lying, awkward pitch, physical comedy, romantic reaction, angry confrontation, anime exaggeration, deadpan humor, emotional realization, visual reveal, and a no-reference scene using real Gemini and Parallel calls.

| Metric | Result |
| --- | ---: |
| Precision@3 | 100.0% |
| Precision@5 | 100.0% |
| Article contamination | 0.0% |
| Valid direct artifacts | 100.0% |
| Valid source URLs | 100.0% |
| Strict requested-type adherence | 64.7% |

The no-reference scene correctly produced no plan, no queries, and no results. Strict Film/TV/Anime searches sometimes produced zero or fewer than three promoted artifacts; the gate favored an honest empty result over padding the UI with articles or weak topic pages.

## Five-scene A/B audit

The first five scenes also ran through the prior Phase 2 artifact-query builder and current quality gate, isolating retrieval-query quality from ranking changes. The v2 planner produced behavior-, performance-, platform-, and culture-language query families rather than only expanding Phase 2 phrases.

| Scene | Prior-path observation | V2 observation |
| --- | --- | --- |
| Caught lying | Two valid but non-Anime artifacts led | Four promoted artifacts; top result was an Anime moment at 90 |
| Awkward pitch | Two short-form artifacts led | Five promoted artifacts; top short-form result scored 92 after diagnosed reformulation |
| Physical comedy | Generic situation wording | Planner added body-action, consequence, GIF, and meme families |
| Romantic reaction | Generic emotional wording | Planner separated facial, performance, flowers/reunion, and short-form intents |
| Angry confrontation | No prior promoted artifacts | V2 preserved an honest empty Film result after one reformulation |

This is a live observational benchmark, not a statistically powered relevance study. Parallel index variation and Gemini assessment variance mean repeated runs may return different artifacts.

## Production preference smoke tests

All deployed calls returned HTTP 200 through the managed pipeline using Firestore project `prod-firestore-e2e-20260907`.

| Preference | Results | Retry | Top evidence |
| --- | ---: | ---: | --- |
| Anime + Facial Expression | 5 | 1 | Anime moment, score 87 |
| TikTok/Short-form + Comedic Timing | 6 | 0 | Viral video, score 94 |
| Memes + Situation | 5 | 1 | GIF, score 73 |
| Any + Best Overall | 1 | 1 | Film/TV moment, score 88 |
| Niche recognition | 2 | 1 | GIFs scored 57/56 |
| Iconic recognition | 4 | 1 | TikTok/GIF results scored 71/66/65 |

Recognition currently affects deterministic rank order, but recognizability is inferred because providers do not consistently supply view/share metadata. The niche run still retrieved recognizable GIFs and penalized them; stronger popularity metadata is needed to improve recall at the low end.

## Current weaknesses and next measurement

- Managed Agent Engine requests are slow because candidates are assessed independently and the retry is serial; bounded batch assessment or controlled concurrency is the next latency improvement.
- Requested-type adherence is the primary quality gap. Cross-type artifacts can survive when they are creatively strong; the UI labels the actual assessed type.
- Era scoring is neutral without trustworthy dates. Provider metadata should be expanded before era becomes a hard filter.
- Recognizability is explicitly labeled as inferred. Future providers should supply verifiable reach or engagement evidence.
- The evaluation reports URL and classifier validity, not successful media playback on every third-party platform.

Raw deployed smoke evidence is stored in `docs/reference_quality_v2_production.json`. Re-run the local benchmark with `python -m backend.scripts.reference_quality_v2_eval` and the deployed suite with `python -m backend.scripts.production_reference_v2_smoke`.

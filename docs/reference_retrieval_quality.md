# Reference retrieval quality audit

## Decision

The retrieval pipeline now optimizes for direct visual cultural artifacts rather than topical information. Top Results require a real Parallel result, a recognized direct-artifact URL pattern, Gemini-validated performance relevance, artifact quality of at least 60, and an application-calculated match score of at least 55.

## Before and after

| Stage | Before audit | After redesign |
|---|---|---|
| Phase 2 query intent | Topic-oriented phrases could produce queries such as `worst startup presentation mistakes` | Each Gemini query is 3–6 words and contains observable performance plus reaction/meme/GIF/TikTok/Reel/Shorts vocabulary |
| Search plan | Semantic searches only | Up to three broad artifact searches plus two source-targeted searches per round |
| Fallback | Triggered by raw result count | Triggered when fewer than three direct artifacts survive; maximum two rounds |
| Candidate handling | User filter was copied into `reference_type` | URL evidence assigns `CulturalReferenceType` and `SourcePlatform`; articles and collection pages are blocked |
| Enrichment | Search excerpts only | Parallel Extract selectively enriches up to four ambiguous or sparse shortlisted pages in the shared search session |
| Ranking | Semantic similarity and topic-adjacent pages could rank | Visual/action 25%, situation 20%, performance/body language 20%, timing 15%, emotion 10%, recognizability 10% |
| Display | Any sufficiently scored result could appear | Only direct artifact pages can appear; extracted articles cannot be promoted into the original artifact |

Observed baseline examples were Business Insider/advice pages for startup pitches and a generic GIPHY `/explore` collection for caught-lying queries. These are now withheld by deterministic provenance gates.

## Official Parallel patterns

- [Search best practices](https://docs.parallel.ai/search/best-practices): concise 3–6 word queries, a self-contained objective, two to three primary query variants, and bounded advanced settings.
- [Source Policy](https://docs.parallel.ai/resources/source-policy): hard domain inclusion is used only for dedicated platform calls; broad open-web calls remain in the same round.
- [Extract API](https://docs.parallel.ai/api-reference/extract/extract): shortlisted URLs are selectively enriched with the same session identifier and a focused artifact-verification objective.

## Final live manual audit — 2026-09-05

The audit command was:

```powershell
.\.venv\Scripts\python.exe -m backend.scripts.reference_quality_audit
```

### Scene A — caught lying with frosting evidence

Gemini classified the scene as a strong opportunity (85) and generated queries including `caught red handed reaction GIF`, `smile freezes eyes drop meme`, and `caught in lie visual reaction meme`. Parallel returned 23 deduplicated pages; 18 failed deterministic pre-ranking gates.

| Candidate inspected | Verdict |
|---|---|
| Imgur — “Caught in the act” direct gallery | Legitimate artifact; match varied by available excerpt |
| Know Your Meme — “Reacting To Me Lying” | Legitimate meme page |
| Tenor — “Face Drop Smile Drop GIF” | Legitimate direct GIF and strongest performance match |
| Tenor — “Big Smile Brain Freeze” | Legitimate artifact but weak situational match |
| Tenor — “Side Eye Meme GIF” | Legitimate artifact but weaker performance match |

The initial definitive pass conservatively displayed no Scene A result because all model match scores fell below 55. An immediate diagnostic pass scored “Face Drop Smile Drop GIF” at 91 (visual 95, acting 95, timing 90), confirming useful retrieval but also revealing score variance; ranking temperature was therefore reduced to zero. The final FastAPI-level smoke test then returned one direct Tenor “Oh Awkward / I See / Realization” GIF at score 84 from 22 raw candidates, with 21 withheld and two selectively extracted.

### Scene B — absurd startup pitch

Gemini classified the scene as a strong opportunity (85) and generated `awkward silence reaction GIF`, `confident absurd pitch viral clip`, and related platform-targeted variants. Parallel returned 20 pages; only two passed every display gate:

| Displayed reference | Type | Score | Manual verdict |
|---|---|---:|---|
| Yarn — “I'm pretty confident about all this,” *Pitch Perfect* | Film/TV moment | 82 | Legitimate direct performance clip |
| Imgur — “Awkward silence” | Reaction meme | 67 | Legitimate direct visual artifact |

Pinterest idea pages, Instagram profiles, GIF collection/search pages, generic news, and an article describing a viral clip were withheld. The inspected shortlist also contained legitimate but weakly matched meme posts that correctly did not enter Top Results.

### Scene C — quiet emotional library scene

Gemini returned `no reference needed` with score 15 and zero queries. Parallel and ranking were not called, so no irrelevant meme was forced.

## Measured quality

The final production-state checks displayed three legitimate artifacts out of three displayed results across Scenes A and B: **100% precision**, exceeding the 80% requirement. Scene C correctly displayed none. This is a precision result, not a recall claim; Scene A demonstrated that sparse excerpts and Gemini score variance can still suppress a useful direct artifact.

## Remaining technical debt

- Add an offline labeled retrieval-evaluation corpus so precision and recall are measured across stable fixtures rather than live-web variation.
- Add platform metadata or preview APIs only where terms and authentication permit; neutral placeholders remain the safe default.
- Monitor direct YouTube watch-page quality because a video URL proves an artifact exists but does not guarantee cultural recognizability.
- Consider retaining non-artifact pages in a separate “Related Research” response only if the product later needs that surface; they must never enter Ranked References.

# backend/app/tools/parallel_search.py
"""Official Parallel Search SDK adapter for live cultural-reference discovery."""

import hashlib
import os
from collections.abc import Callable, Sequence
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import uuid4

import parallel
from dotenv import load_dotenv
from parallel import Parallel
from pydantic import ValidationError

from backend.app.schemas.reference import (
    CulturalReferenceCandidate,
    CulturalReferenceType,
    CulturalSearchResult,
    MatchFor,
    ReferenceEra,
    ReferenceType,
    SearchQueryFailure,
)
from backend.app.services.reference_quality import (
    DIRECT_ARTIFACT_TYPES,
    classify_candidate,
    is_promising_ambiguous_candidate,
)


# Provide an explicit configuration error without leaking credential values.
class ParallelConfigurationError(RuntimeError):
    """Raised when the server-side Parallel API key is unavailable."""


# Represent a terminal provider failure after all useful queries fail.
class ParallelSearchError(RuntimeError):
    """Raised when Parallel Search cannot return any usable query response."""

    # Preserve an HTTP status category for the FastAPI boundary.
    def __init__(self, message: str, status_code: int = 502) -> None:
        """Initialize a sanitized provider error and API-facing status code."""

        super().__init__(message)
        self.status_code = status_code


# Create the official client lazily so application startup remains credential-free.
def create_parallel_client() -> Parallel:
    """Create an official Parallel SDK client from server environment settings."""

    try:
        load_dotenv()
        api_key = os.getenv("PARALLEL_API_KEY")
        if not api_key:
            raise ParallelConfigurationError(
                "PARALLEL_API_KEY is not configured on the backend."
            )
        return Parallel(api_key=api_key, timeout=20.0, max_retries=2)
    except ParallelConfigurationError:
        raise
    except Exception as exc:
        raise ParallelConfigurationError(
            f"Parallel client configuration failed: {exc}"
        ) from exc


# Normalize provider URLs for stable identifiers and aggressive deduplication.
def canonicalize_url(url: str) -> str:
    """Remove fragments and tracking parameters while preserving the source URL."""

    parsed = urlsplit(url.strip())
    hostname = (parsed.hostname or "").lower()
    if hostname.startswith("www."):
        hostname = hostname[4:]
    port = f":{parsed.port}" if parsed.port else ""
    netloc = f"{hostname}{port}"
    ignored_parameters = {
        "fbclid",
        "gclid",
        "mc_cid",
        "mc_eid",
        "ref",
        "source",
    }
    query_items = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in ignored_parameters
    ]
    path = parsed.path.rstrip("/") or "/"
    return urlunsplit((parsed.scheme.lower(), netloc, path, urlencode(query_items), ""))


# Remove duplicate URLs and duplicate titled pages while preserving discovery order.
def deduplicate_candidates(
    candidates: Sequence[CulturalReferenceCandidate],
    limit: int | None = None,
) -> list[CulturalReferenceCandidate]:
    """Return unique candidates in their original Parallel relevance order."""

    unique: list[CulturalReferenceCandidate] = []
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    for candidate in candidates:
        canonical_url = canonicalize_url(str(candidate.url))
        normalized_title = "".join(
            character.lower()
            for character in candidate.title
            if character.isalnum() or character.isspace()
        )
        normalized_title = " ".join(normalized_title.split())
        if canonical_url in seen_urls or (len(normalized_title) >= 12 and normalized_title in seen_titles):
            # Merge query provenance into the first canonical artifact.
            for index, existing in enumerate(unique):
                existing_title = " ".join("".join(character.lower() for character in existing.title if character.isalnum() or character.isspace()).split())
                if canonicalize_url(str(existing.url)) == canonical_url or (normalized_title and existing_title == normalized_title):
                    merged_queries = list(dict.fromkeys([*existing.discovered_from_queries, *candidate.discovered_from_queries, candidate.discovered_from_query]))
                    unique[index] = existing.model_copy(update={"discovered_from_queries": merged_queries})
                    break
            continue
        seen_urls.add(canonical_url)
        if normalized_title:
            seen_titles.add(normalized_title)
        unique.append(candidate)
        if limit is not None and len(unique) >= limit:
            break
    return unique


# Adapt Parallel's response model into a strict, provider-neutral candidate schema.
def normalize_parallel_result(
    result: object,
    query: str,
    reference_type: ReferenceType,
    search_id: str,
    session_id: str,
    position: int,
) -> CulturalReferenceCandidate:
    """Normalize one official SDK search result without inventing source facts."""

    raw_url = str(_read_value(result, "url", "")).strip()
    parsed_url = urlsplit(raw_url)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.hostname:
        raise ValueError("Parallel result did not contain a valid public URL.")

    excerpts = list(_read_value(result, "excerpts", []) or [])
    snippet = "\n\n".join(str(value).strip() for value in excerpts if str(value).strip())
    snippet = snippet[:2400]
    raw_title = _read_value(result, "title", None)
    title = str(raw_title).strip() if raw_title else parsed_url.hostname
    canonical_url = canonicalize_url(raw_url)
    candidate_id = hashlib.sha256(canonical_url.encode("utf-8")).hexdigest()[:16]
    normalized_type = (
        reference_type
        if reference_type != ReferenceType.ALL
        else ReferenceType.UNCLASSIFIED
    )

    candidate = CulturalReferenceCandidate(
        id=f"ref_{candidate_id}",
        title=title,
        url=raw_url,
        source_domain=(parsed_url.hostname or "").removeprefix("www."),
        snippet=snippet,
        image_url=None,
        reference_type=normalized_type,
        discovered_from_query=query,
        discovered_from_queries=[query],
        search_family=_infer_search_family(query),
        published_at=_read_value(result, "publish_date", None),
        source_metadata={
            "provider": "parallel",
            "parallel_search_id": search_id,
            "parallel_session_id": session_id,
            "parallel_result_position": position,
            "parallel_excerpt_count": len(excerpts),
        },
    )
    return classify_candidate(candidate)


# Keep the provider adapter injectable for unit tests and future async migration.
class ParallelSearchClient:
    """Search each Gemini query through the official Parallel Python SDK."""

    # Defer key validation until the first real search request.
    def __init__(
        self,
        client: Parallel | None = None,
        client_factory: Callable[[], Parallel] = create_parallel_client,
    ) -> None:
        """Initialize the adapter with an optional official SDK-compatible client."""

        self._client = client
        self._client_factory = client_factory

    # Execute independent queries so one provider failure does not discard the batch.
    def search_cultural_references(
        self,
        queries: Sequence[str],
        reference_type: ReferenceType = ReferenceType.ALL,
        era: ReferenceEra = ReferenceEra.ANY,
        match_for: MatchFor = MatchFor.ALL,
        obscurity: int = 50,
        max_results: int = 24,
        objective: str | None = None,
        session_id: str | None = None,
    ) -> CulturalSearchResult:
        """Call Parallel Search at runtime and normalize traceable web results."""

        cleaned_queries = _prepare_queries(queries)
        if not cleaned_queries:
            return CulturalSearchResult(candidates=[], searched_queries=[])

        client = self._get_client()
        candidates: list[CulturalReferenceCandidate] = []
        searched_queries: list[str] = []
        failed_queries: list[SearchQueryFailure] = []
        warnings: list[str] = []
        session_ids: list[str] = []
        successful_calls = 0
        request_session_id = session_id or f"icra_{uuid4().hex}"
        results_per_query = max(3, min(6, (max_results + len(cleaned_queries) - 1) // len(cleaned_queries)))
        search_objective = objective or _build_objective(
            reference_type, era, match_for, obscurity
        )

        for query in cleaned_queries:
            searched_queries.append(query)
            try:
                advanced_settings: dict[str, object] = {
                    "max_results": results_per_query
                }
                source_domain = _source_target_domain(query)
                if source_domain:
                    advanced_settings["source_policy"] = {
                        "include_domains": [source_domain]
                    }
                response = client.search(
                    objective=search_objective,
                    search_queries=[query],
                    mode="fast",
                    max_chars_total=4000,
                    client_model=os.getenv("GOOGLE_GENAI_MODEL", "gemini-2.5-flash"),
                    session_id=request_session_id,
                    advanced_settings=advanced_settings,
                )
                successful_calls += 1
                search_id = str(_read_value(response, "search_id", ""))
                session_id = str(_read_value(response, "session_id", ""))
                if session_id and session_id not in session_ids:
                    session_ids.append(session_id)
                for warning in _read_value(response, "warnings", []) or []:
                    warnings.append(str(warning))
                for position, result in enumerate(
                    _read_value(response, "results", []) or [], start=1
                ):
                    try:
                        candidates.append(
                            normalize_parallel_result(
                                result,
                                query,
                                reference_type,
                                search_id,
                                session_id,
                                position,
                            )
                        )
                    except (ValidationError, ValueError, TypeError):
                        warnings.append(
                            f"Parallel returned one malformed result for query: {query}"
                        )
            except Exception as exc:
                failed_queries.append(_normalize_error(query, exc))

        if successful_calls == 0 and failed_queries:
            status_code = _aggregate_status_code(failed_queries)
            raise ParallelSearchError(
                "All Parallel Search queries failed. Verify credentials, quota, and connectivity.",
                status_code=status_code,
            )

        return CulturalSearchResult(
            candidates=deduplicate_candidates(candidates, limit=max_results),
            searched_queries=searched_queries,
            failed_queries=failed_queries,
            warnings=warnings,
            session_ids=session_ids,
            raw_candidate_count=len(deduplicate_candidates(candidates)),
        )

    # Enrich only ambiguous shortlisted URLs through the official Extract API.
    def enrich_ambiguous_candidates(
        self,
        candidates: Sequence[CulturalReferenceCandidate],
        objective: str,
        search_queries: Sequence[str],
        limit: int = 4,
    ) -> tuple[list[CulturalReferenceCandidate], list[str], int]:
        """Add focused excerpts to ambiguous candidates while controlling cost."""

        selected = [
            candidate
            for candidate in candidates
            if (
                candidate.cultural_reference_type == CulturalReferenceType.OTHER
                and is_promising_ambiguous_candidate(candidate)
            )
            or (
                candidate.cultural_reference_type in DIRECT_ARTIFACT_TYPES
                and len(candidate.snippet.strip()) < 120
            )
        ][:limit]
        if not selected:
            return list(candidates), [], 0

        session_id = str(
            selected[0].source_metadata.get("parallel_session_id")
            or f"icra_{uuid4().hex}"
        )
        try:
            response = self._get_client().extract(
                urls=[str(candidate.url) for candidate in selected],
                objective=(
                    f"{objective} Determine whether each page is a direct visual cultural "
                    "artifact such as a post, video, GIF, meme, or identifiable scene; "
                    "extract evidence describing the visible performance moment."
                ),
                search_queries=_prepare_queries(search_queries)[:3],
                session_id=session_id,
                max_chars_total=8000,
                client_model=os.getenv("GOOGLE_GENAI_MODEL", "gemini-2.5-flash"),
            )
        except Exception as exc:
            return (
                list(candidates),
                [f"Parallel Extract was unavailable: {type(exc).__name__}."],
                0,
            )

        extracted_by_url: dict[str, object] = {}
        for result in _read_value(response, "results", []) or []:
            result_url = str(_read_value(result, "url", ""))
            if result_url:
                extracted_by_url[canonicalize_url(result_url)] = result

        extract_id = str(_read_value(response, "extract_id", ""))
        enriched: list[CulturalReferenceCandidate] = []
        enriched_count = 0
        for candidate in candidates:
            result = extracted_by_url.get(canonicalize_url(str(candidate.url)))
            if result is None:
                enriched.append(candidate)
                continue
            excerpts = [
                str(excerpt).strip()
                for excerpt in (_read_value(result, "excerpts", []) or [])
                if str(excerpt).strip()
            ]
            snippet = "\n\n".join(excerpts)[:3000] or candidate.snippet
            metadata = {
                **candidate.source_metadata,
                "parallel_extracted": True,
                "parallel_extract_id": extract_id,
            }
            enriched.append(
                classify_candidate(
                    candidate.model_copy(
                        update={"snippet": snippet, "source_metadata": metadata}
                    )
                )
            )
            enriched_count += 1

        warnings = [
            "Parallel Extract could not fetch one shortlisted URL."
            for _ in (_read_value(response, "errors", []) or [])
        ]
        return enriched, warnings, enriched_count

    # Create the provider client only after validated queries require a live call.
    def _get_client(self) -> Parallel:
        """Return the official Parallel client, creating it when necessary."""

        if self._client is None:
            self._client = self._client_factory()
        return self._client


# Provide the requested reusable functional entry point for other agents.
def search_cultural_references(
    queries: Sequence[str],
    reference_type: ReferenceType = ReferenceType.ALL,
    era: ReferenceEra = ReferenceEra.ANY,
    match_for: MatchFor = MatchFor.ALL,
    obscurity: int = 50,
    max_results: int = 24,
) -> CulturalSearchResult:
    """Search real cultural references through a server-side Parallel client."""

    return ParallelSearchClient().search_cultural_references(
        queries=queries,
        reference_type=reference_type,
        era=era,
        match_for=match_for,
        obscurity=obscurity,
        max_results=max_results,
    )


# Read response fields from either official Pydantic models or test dictionaries.
def _read_value(value: object, name: str, default: object) -> object:
    """Return a named field from an SDK model or dictionary."""

    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


# Constrain generated queries to the official Search API's concise input guidance.
def _prepare_queries(queries: Sequence[str]) -> list[str]:
    """Return unique concise queries with an eight-call provider ceiling."""

    prepared: list[str] = []
    seen: set[str] = set()
    for query in queries:
        concise = " ".join(str(query).strip().split()[:6])[:200]
        key = concise.casefold()
        if concise and key not in seen:
            prepared.append(concise)
            seen.add(key)
        if len(prepared) == 8:
            break
    return prepared


# Classify query provenance without changing provider-owned result facts.
def _infer_search_family(query: str) -> str:
    """Return the dominant creative query family for transparency."""

    words = set(query.casefold().replace("/", " ").split())
    families = (
        ("platform", {"tiktok", "reels", "instagram", "shorts", "giphy", "tenor"}),
        ("facial_reaction", {"face", "facial", "eyes", "smile", "expression", "reaction"}),
        ("physical_action", {"fall", "trip", "slapstick", "movement", "physical", "body"}),
        ("performance", {"acting", "performance", "deadpan", "delivery"}),
        ("emotional_reversal", {"realization", "embarrassment", "romantic", "angry", "emotion"}),
        ("internet_terminology", {"meme", "gif", "viral"}),
    )
    for family, markers in families:
        if words.intersection(markers):
            return family
    return "situation"


# Translate a site-targeted query into Parallel's hard per-call source policy.
def _source_target_domain(query: str) -> str | None:
    """Return the apex domain from a leading site operator when present."""

    first_word = query.strip().split(maxsplit=1)[0] if query.strip() else ""
    if not first_word.casefold().startswith("site:"):
        return None
    target = first_word[5:].split("/", maxsplit=1)[0].strip().casefold()
    return target.removeprefix("www.") or None


# Give Parallel the semantic goal while keeping keyword queries compact.
def _build_objective(
    reference_type: ReferenceType,
    era: ReferenceEra,
    match_for: MatchFor,
    obscurity: int,
) -> str:
    """Translate user filters into a self-contained Parallel search objective."""

    type_labels = {
        ReferenceType.ALL: "memes, internet culture, film, television, anime, and viral moments",
        ReferenceType.MEMES: "memes",
        ReferenceType.INTERNET_CULTURE: "internet culture",
        ReferenceType.REACTION_GIFS: "reaction GIFs",
        ReferenceType.FILM: "film moments",
        ReferenceType.TV: "television moments",
        ReferenceType.ANIME: "anime",
        ReferenceType.TIKTOK_SHORT_FORM: "TikTok, Reels, and YouTube Shorts",
        ReferenceType.INSTAGRAM_REELS: "Instagram Reels",
        ReferenceType.UNCLASSIFIED: "cultural references",
    }
    type_text = type_labels[reference_type]
    era_text = "any era" if era == ReferenceEra.ANY else era.value
    match_text = (
        "acting, situation, visual composition, and timing"
        if match_for == MatchFor.ALL
        else match_for.value
    )
    obscurity_text = (
        "widely recognizable mainstream references"
        if obscurity <= 30
        else "niche or cult references"
        if obscurity >= 70
        else "a balanced mix of recognizable and less obvious references"
    )
    return (
        "Find real, traceable cultural reference pages useful for directing a "
        f"screenplay scene. Prioritize {type_text} from {era_text}, matching {match_text}, "
        f"with {obscurity_text}. Return source pages that describe or show the moment."
    )


# Translate official SDK errors into safe query-level diagnostics.
def _normalize_error(query: str, exc: Exception) -> SearchQueryFailure:
    """Map a Parallel SDK exception to a sanitized partial-failure record."""

    if isinstance(exc, parallel.AuthenticationError):
        return SearchQueryFailure(
            query=query,
            error_type="authentication",
            message="Parallel rejected the backend credentials.",
        )
    if isinstance(exc, parallel.RateLimitError):
        return SearchQueryFailure(
            query=query,
            error_type="rate_limit",
            message="Parallel rate limit was reached.",
        )
    if isinstance(exc, parallel.APITimeoutError):
        return SearchQueryFailure(
            query=query,
            error_type="timeout",
            message="Parallel Search timed out.",
        )
    if isinstance(exc, parallel.APIConnectionError):
        return SearchQueryFailure(
            query=query,
            error_type="connection",
            message="Parallel Search could not be reached.",
        )
    if isinstance(exc, parallel.APIStatusError):
        return SearchQueryFailure(
            query=query,
            error_type=f"provider_{exc.status_code}",
            message="Parallel Search returned an upstream error.",
        )
    return SearchQueryFailure(
        query=query,
        error_type="unexpected",
        message="Parallel Search returned an unexpected error.",
    )


# Select an API status that preserves actionable rate-limit and timeout states.
def _aggregate_status_code(failures: Sequence[SearchQueryFailure]) -> int:
    """Return the most useful HTTP status for an all-query failure."""

    error_types = {failure.error_type for failure in failures}
    if "rate_limit" in error_types:
        return 429
    if "timeout" in error_types or "connection" in error_types:
        return 504
    return 502

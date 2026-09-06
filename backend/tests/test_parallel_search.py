# backend/tests/test_parallel_search.py
"""Tests for the official Parallel client wrapper and result normalization."""

from types import SimpleNamespace

from backend.app.schemas.reference import ReferenceType
from backend.app.tools.parallel_search import (
    ParallelConfigurationError,
    ParallelSearchClient,
    ParallelSearchError,
    canonicalize_url,
    create_parallel_client,
)


# Simulate query-specific Parallel responses without making network calls.
class FakeParallelClient:
    """Return configured SDK-shaped search responses for each query."""

    def __init__(
        self,
        responses: dict[str, object],
        extract_response: object | None = None,
    ) -> None:
        """Store query outcomes and captured request arguments."""

        self.responses = responses
        self.requests: list[dict[str, object]] = []
        self.extract_response = extract_response
        self.extract_requests: list[dict[str, object]] = []

    def search(self, **kwargs: object) -> object:
        """Return or raise the configured outcome for one query."""

        self.requests.append(kwargs)
        query = kwargs["search_queries"][0]
        response = self.responses[str(query)]
        if isinstance(response, Exception):
            raise response
        return response

    def extract(self, **kwargs: object) -> object:
        """Capture selective Extract requests and return configured content."""

        self.extract_requests.append(kwargs)
        if isinstance(self.extract_response, Exception):
            raise self.extract_response
        return self.extract_response


# Build an official-response-shaped object with traceable web results.
def build_response(*results: object) -> SimpleNamespace:
    """Return a compact Parallel Search response fixture."""

    return SimpleNamespace(
        search_id="search_test",
        session_id="session_test",
        warnings=None,
        results=list(results),
    )


# Build one result fixture using fields supplied by the Search API.
def build_result(url: str, title: str) -> SimpleNamespace:
    """Return a Parallel web-result fixture."""

    return SimpleNamespace(
        url=url,
        title=title,
        publish_date="2024-01-15",
        excerpts=["A useful real-page excerpt."],
    )


# Confirm factual fields, provider metadata, limits, and official request options.
def test_parallel_wrapper_normalizes_real_fields() -> None:
    """Normalize a Parallel response into the raw candidate schema."""

    fake = FakeParallelClient(
        {
            "caught lying reaction meme": build_response(
                build_result("https://example.com/reference", "Caught reaction")
            )
        }
    )
    wrapper = ParallelSearchClient(client=fake)

    result = wrapper.search_cultural_references(
        ["caught lying reaction meme"],
        reference_type=ReferenceType.MEMES,
        max_results=6,
    )

    candidate = result.candidates[0]
    assert candidate.title == "Caught reaction"
    assert str(candidate.url) == "https://example.com/reference"
    assert candidate.source_domain == "example.com"
    assert candidate.published_at == "2024-01-15"
    assert candidate.source_metadata["provider"] == "parallel"
    assert fake.requests[0]["mode"] == "fast"
    assert fake.requests[0]["advanced_settings"] == {"max_results": 6}


# Confirm tracking variants and duplicate titles collapse into one candidate.
def test_parallel_wrapper_deduplicates_overlapping_results() -> None:
    """Deduplicate results found by multiple semantic queries."""

    fake = FakeParallelClient(
        {
            "caught lying reaction": build_response(
                build_result(
                    "https://www.example.com/reference?utm_source=test",
                    "Caught reaction",
                )
            ),
            "awkward realization scene": build_response(
                build_result("https://example.com/reference", "Caught reaction")
            ),
        }
    )

    result = ParallelSearchClient(client=fake).search_cultural_references(
        ["caught lying reaction", "awkward realization scene"],
        max_results=10,
    )

    assert len(result.candidates) == 1
    assert canonicalize_url(str(result.candidates[0].url)) == (
        "https://example.com/reference"
    )


# Confirm an empty successful provider response remains a valid no-results outcome.
def test_parallel_wrapper_handles_empty_results() -> None:
    """Return an empty candidate collection without fabricating references."""

    fake = FakeParallelClient({"rare reaction scene": build_response()})
    result = ParallelSearchClient(client=fake).search_cultural_references(
        ["rare reaction scene"]
    )

    assert result.candidates == []
    assert result.failed_queries == []


# Confirm one failed query does not discard successful traceable results.
def test_parallel_wrapper_allows_partial_success() -> None:
    """Preserve candidates when another query fails."""

    fake = FakeParallelClient(
        {
            "working query": build_response(
                build_result("https://example.org/moment", "Real moment")
            ),
            "failing query": RuntimeError("provider unavailable"),
        }
    )
    result = ParallelSearchClient(client=fake).search_cultural_references(
        ["working query", "failing query"]
    )

    assert len(result.candidates) == 1
    assert result.partial_success is True
    assert result.failed_queries[0].query == "failing query"


# Confirm a terminal provider outage is represented by one domain error.
def test_parallel_wrapper_raises_when_every_query_fails() -> None:
    """Raise a ParallelSearchError after all query calls fail."""

    fake = FakeParallelClient(
        {
            "first query": RuntimeError("failed"),
            "second query": RuntimeError("failed"),
        }
    )
    try:
        ParallelSearchClient(client=fake).search_cultural_references(
            ["first query", "second query"]
        )
    except ParallelSearchError as exc:
        assert exc.status_code == 502
        return
    raise AssertionError("Expected every failed Parallel query to raise")


# Confirm the provider secret is required only on the backend at runtime.
def test_parallel_client_requires_server_api_key(monkeypatch: object) -> None:
    """Raise a clear configuration error when the server key is absent."""

    monkeypatch.setenv("PARALLEL_API_KEY", "")
    try:
        create_parallel_client()
    except ParallelConfigurationError as exc:
        assert "PARALLEL_API_KEY" in str(exc)
        return
    raise AssertionError("Expected a missing Parallel API key to be rejected")


# Confirm leading site operators receive an explicit per-call source policy.
def test_parallel_wrapper_applies_source_policy_to_targeted_query() -> None:
    """Hard-target TikTok only for the dedicated platform search call."""

    query = "site:tiktok.com awkward founder reaction video"
    fake = FakeParallelClient({query: build_response()})

    ParallelSearchClient(client=fake).search_cultural_references([query])

    settings = fake.requests[0]["advanced_settings"]
    assert settings["source_policy"] == {"include_domains": ["tiktok.com"]}
    assert fake.requests[0]["session_id"].startswith("icra_")


# Confirm ambiguous shortlist enrichment uses the official Extract method once.
def test_parallel_wrapper_selectively_extracts_ambiguous_candidate() -> None:
    """Enrich an unknown page and retain traceable Extract metadata."""

    candidate = build_result("https://example.com/moment", "Unknown reaction clip")
    search_response = build_response(candidate)
    extract_result = SimpleNamespace(
        url="https://example.com/moment",
        excerpts=["A visible reaction clip shows everyone staring in silence."],
    )
    extract_response = SimpleNamespace(
        extract_id="extract_test",
        results=[extract_result],
        errors=[],
    )
    fake = FakeParallelClient(
        {"awkward reaction clip": search_response},
        extract_response=extract_response,
    )
    wrapper = ParallelSearchClient(client=fake)
    search_result = wrapper.search_cultural_references(["awkward reaction clip"])

    enriched, warnings, count = wrapper.enrich_ambiguous_candidates(
        search_result.candidates,
        objective="Find a direct visual reaction artifact.",
        search_queries=["awkward reaction clip"],
    )

    assert count == 1
    assert warnings == []
    assert enriched[0].source_metadata["parallel_extracted"] is True
    assert "visible reaction clip" in enriched[0].snippet

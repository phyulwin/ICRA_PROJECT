# backend/tests/test_reference_preview.py
"""Tests for safe source-provided cultural-reference preview images."""

from backend.app.schemas.reference import (
    CulturalReferenceCandidate,
    ReferenceType,
)
from backend.app.services.reference_preview import ReferencePreviewResolver


# Build one minimal candidate for preview enrichment tests.
def build_candidate(url: str) -> CulturalReferenceCandidate:
    """Return a traceable candidate without a preview image."""

    return CulturalReferenceCandidate(
        id="ref_preview",
        title="Visual reaction",
        url=url,
        source_domain="example.com",
        snippet="A direct visual reaction artifact.",
        reference_type=ReferenceType.ALL,
        discovered_from_query="awkward reaction GIF",
    )


# Confirm YouTube thumbnails are derived without an additional page request.
def test_resolver_builds_youtube_thumbnail_without_fetch() -> None:
    """Use a stable YouTube video identifier for the preview URL."""

    def fail_if_called(_: str) -> str | None:
        """Fail if deterministic YouTube handling attempts an HTML request."""

        raise AssertionError("YouTube preview should not fetch HTML")

    resolver = ReferencePreviewResolver(fetch_html=fail_if_called)
    candidate = build_candidate("https://www.youtube.com/watch?v=abc_123-Z")

    enriched = resolver.enrich_candidate(candidate)

    assert str(enriched.image_url) == (
        "https://i.ytimg.com/vi/abc_123-Z/hqdefault.jpg"
    )


# Confirm trusted Open Graph metadata becomes a browser-displayable preview.
def test_resolver_reads_trusted_open_graph_image() -> None:
    """Resolve a Tenor-provided image without inventing unrelated artwork."""

    html = (
        '<html><head><meta property="og:image" '
        'content="https://media.tenor.com/example.gif"></head></html>'
    )
    resolver = ReferencePreviewResolver(fetch_html=lambda _: html)
    candidate = build_candidate("https://tenor.com/view/example-gif-123")

    enriched = resolver.enrich_candidate(candidate)

    assert str(enriched.image_url) == "https://media.tenor.com/example.gif"


# Confirm unknown domains cannot trigger server-side page retrieval.
def test_resolver_does_not_fetch_untrusted_source() -> None:
    """Retain the neutral placeholder for an unapproved source domain."""

    def fail_if_called(_: str) -> str | None:
        """Fail if an untrusted URL reaches the injected fetcher."""

        raise AssertionError("Untrusted source should not be fetched")

    resolver = ReferencePreviewResolver(fetch_html=fail_if_called)
    candidate = build_candidate("https://example.com/reference")

    enriched = resolver.enrich_candidate(candidate)

    assert enriched.image_url is None

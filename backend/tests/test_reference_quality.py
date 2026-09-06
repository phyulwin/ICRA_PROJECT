# backend/tests/test_reference_quality.py
"""Tests for deterministic cultural-artifact query and candidate quality gates."""

from backend.app.schemas.reference import (
    CulturalReferenceCandidate,
    CulturalReferenceType,
    ReferenceType,
    SourcePlatform,
)
from backend.app.services.reference_quality import (
    build_artifact_queries,
    classify_candidate,
    filter_informational_candidates,
)


# Build one raw Parallel candidate for deterministic classification tests.
def build_candidate(url: str, title: str, snippet: str = "") -> CulturalReferenceCandidate:
    """Return a candidate before artifact classification."""

    return CulturalReferenceCandidate(
        id="ref_test",
        title=title,
        url=url,
        source_domain="example.com",
        snippet=snippet,
        reference_type=ReferenceType.ALL,
        discovered_from_query="awkward startup reaction meme",
    )


# Confirm retrieval always includes broad intent and dedicated platform targeting.
def test_build_artifact_queries_adds_broad_and_source_targeted_searches() -> None:
    """Create artifact-oriented queries without replacing broad discovery."""

    queries = build_artifact_queries(
        ["bad startup pitch", "everyone silently stares"],
        ReferenceType.INTERNET,
    )

    assert queries[0] == "bad startup pitch reaction meme"
    assert queries[1] == "everyone silently stares reaction meme"
    assert queries[2].startswith("site:tiktok.com ")
    assert queries[3].startswith("site:instagram.com/reel ")


# Confirm direct visual-media URLs receive platform and artifact classifications.
def test_classify_candidate_recognizes_direct_tiktok_video() -> None:
    """Classify a direct TikTok post as a visual artifact."""

    candidate = classify_candidate(
        build_candidate(
            "https://www.tiktok.com/@creator/video/123456",
            "Awkward pitch reaction",
        )
    )

    assert candidate.source_platform == SourcePlatform.TIKTOK
    assert candidate.cultural_reference_type == CulturalReferenceType.TIKTOK


# Confirm same-topic advice pages cannot proceed to model ranking.
def test_filter_informational_candidates_rejects_business_article() -> None:
    """Reject an article despite semantically similar startup-pitch terms."""

    article = build_candidate(
        "https://www.businessinsider.com/presentation-mistakes-2025",
        "11 Presentation Mistakes Founders Make",
    )
    artifact = build_candidate(
        "https://tenor.com/view/awkward-stare-gif-123",
        "Awkward stare GIF",
    )

    accepted, rejected_count = filter_informational_candidates([article, artifact])

    assert rejected_count == 1
    assert accepted[0].cultural_reference_type == CulturalReferenceType.GIF


# Confirm platform search and discovery collections are not treated as artifacts.
def test_filter_informational_candidates_rejects_collection_pages() -> None:
    """Reject generic GIF search and TikTok discovery pages before ranking."""

    candidates = [
        build_candidate(
            "https://tenor.com/search/shocked-audience-gifs",
            "Shocked Audience GIFs",
        ),
        build_candidate(
            "https://www.tiktok.com/discover/disbelief-face-meme",
            "Disbelief Face Meme Slideshow",
        ),
        build_candidate(
            "https://www.pinterest.com/ideas/awkward-reaction-gif/123/",
            "Awkward Reaction GIF",
        ),
        build_candidate(
            "https://gifdb.com/disbelief",
            "Disbelief GIFs - Download and Share",
        ),
    ]

    accepted, rejected_count = filter_informational_candidates(candidates)

    assert accepted == []
    assert rejected_count == 4

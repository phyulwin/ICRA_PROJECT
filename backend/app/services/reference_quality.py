# backend/app/services/reference_quality.py
"""Deterministic cultural-artifact classification and retrieval quality gates."""

from collections.abc import Sequence
from urllib.parse import urlsplit

from backend.app.schemas.reference import (
    CulturalReferenceCandidate,
    CulturalReferenceType,
    ReferenceType,
    SourcePlatform,
)


# Maintain conservative platform targets for dedicated artifact-search calls.
SOURCE_TARGETS: dict[ReferenceType, tuple[str, ...]] = {
    ReferenceType.ALL: (
        "tiktok.com",
        "instagram.com/reel",
        "youtube.com/shorts",
        "giphy.com",
        "tenor.com",
    ),
    ReferenceType.MEMES: ("giphy.com", "tenor.com", "knowyourmeme.com"),
    ReferenceType.REACTION_GIFS: ("giphy.com", "tenor.com"),
    ReferenceType.INTERNET_CULTURE: (
        "tiktok.com",
        "instagram.com/reel",
        "youtube.com/shorts",
        "reddit.com",
    ),
    ReferenceType.TIKTOK_SHORT_FORM: (
        "tiktok.com",
        "instagram.com/reel",
        "youtube.com/shorts",
    ),
    ReferenceType.FILM: ("youtube.com", "getyarn.io"),
    ReferenceType.TV: ("youtube.com", "getyarn.io"),
    ReferenceType.INSTAGRAM_REELS: ("instagram.com/reel",),
    ReferenceType.ANIME: ("youtube.com", "reddit.com"),
    ReferenceType.UNCLASSIFIED: ("giphy.com", "youtube.com/shorts"),
}

ARTICLE_DOMAINS = {
    "businessinsider.com",
    "buzzfeed.com",
    "entrepreneur.com",
    "fastcompany.com",
    "forbes.com",
    "gifdb.com",
    "hbr.org",
    "inc.com",
    "linkedin.com",
    "medium.com",
    "merriam-webster.com",
    "nytimes.com",
    "redbubble.com",
    "techcrunch.com",
    "theguardian.com",
    "tvguide.com",
    "tvtropes.org",
    "wikipedia.org",
    "wordreference.com",
    "yourstory.com",
    "imdb.com",
}

ARTICLE_PATH_MARKERS = (
    "/article/",
    "/articles/",
    "/blog/",
    "/blogs/",
    "/guide/",
    "/how-to/",
    "/insights/",
    "/ideas/",
    "/learn/",
    "/news/",
    "/search/",
    "/explore/",
    "/discover/",
    "/topic/",
    "/tag/",
    "/results/",
    "/popular/",
)

ARTICLE_TEXT_MARKERS = (
    "best practices",
    "common mistakes",
    "explained",
    "full cast",
    "how to ",
    "lessons from",
    "presentation mistakes",
    "things to know",
    "tips for",
    "ways to improve",
    "what is ",
    "why you should",
    "definition & meaning",
    "dictionary of english",
)

ARTIFACT_QUERY_MARKERS = {
    "awkward",
    "clip",
    "comedy",
    "facial",
    "gif",
    "meme",
    "reaction",
    "reel",
    "shorts",
    "stare",
    "tiktok",
    "viral",
    "video",
}

DIRECT_ARTIFACT_TYPES = {
    CulturalReferenceType.REACTION_MEME,
    CulturalReferenceType.VIRAL_VIDEO,
    CulturalReferenceType.TIKTOK,
    CulturalReferenceType.INSTAGRAM_REEL,
    CulturalReferenceType.GIF,
    CulturalReferenceType.FILM_TV_MOMENT,
    CulturalReferenceType.ANIME_MOMENT,
}


# Convert existing Phase 2 intent into broad and source-targeted artifact searches.
def build_artifact_queries(
    queries: Sequence[str],
    reference_type: ReferenceType,
) -> list[str]:
    """Return up to three broad queries plus two dedicated platform queries."""

    broad: list[str] = []
    seen: set[str] = set()
    for query in queries:
        prepared = _make_artifact_oriented(query)
        key = prepared.casefold()
        if prepared and key not in seen:
            broad.append(prepared)
            seen.add(key)
        if len(broad) == 3:
            break

    targets = SOURCE_TARGETS[reference_type]
    targeted: list[str] = []
    for index, query in enumerate(broad[:2]):
        target = targets[index % len(targets)]
        targeted.append(f"site:{target} {query}")
    return [*broad, *targeted]


# Add artifact vocabulary when older stored Phase 2 queries are topic-oriented.
def _make_artifact_oriented(query: str) -> str:
    """Normalize one query and ensure it asks for an observable internet moment."""

    words = str(query).strip().split()[:6]
    lowered = {word.casefold().strip(".,:;!?()[]{}") for word in words}
    if not lowered.intersection(ARTIFACT_QUERY_MARKERS):
        words = [*words[:4], "reaction", "meme"]
    return " ".join(words)[:200]


# Classify immutable source facts using conservative URL and page-title evidence.
def classify_candidate(
    candidate: CulturalReferenceCandidate,
) -> CulturalReferenceCandidate:
    """Attach a deterministic platform and preliminary artifact classification."""

    parsed = urlsplit(str(candidate.url))
    domain = (parsed.hostname or "").casefold().removeprefix("www.")
    path = parsed.path.casefold()
    title_and_snippet = f"{candidate.title} {candidate.snippet}".casefold()
    platform = infer_source_platform(domain)
    artifact_type = _classify_url(domain, path, title_and_snippet)
    return candidate.model_copy(
        update={
            "cultural_reference_type": artifact_type,
            "source_platform": platform,
        }
    )


# Translate well-known source domains into stable frontend platform labels.
def infer_source_platform(domain: str) -> SourcePlatform:
    """Return the recognized platform represented by a hostname."""

    if domain.endswith("tiktok.com"):
        return SourcePlatform.TIKTOK
    if domain.endswith("instagram.com"):
        return SourcePlatform.INSTAGRAM
    if domain.endswith("youtube.com") or domain == "youtu.be":
        return SourcePlatform.YOUTUBE
    if domain.endswith("giphy.com"):
        return SourcePlatform.GIPHY
    if domain.endswith("tenor.com"):
        return SourcePlatform.TENOR
    if domain.endswith("knowyourmeme.com"):
        return SourcePlatform.MEME
    if domain.endswith("insidermemes.com") or domain.endswith("memix.com"):
        return SourcePlatform.MEME
    if domain.endswith("pinterest.com"):
        return SourcePlatform.MEME
    if domain.endswith("imgur.com") or domain.endswith("reactiongifs.com"):
        return SourcePlatform.MEME
    if domain.endswith("reddit.com"):
        return SourcePlatform.REDDIT
    if domain.endswith("getyarn.io"):
        return SourcePlatform.FILM_TV
    return SourcePlatform.WEB


# Identify direct artifact URLs before relying on model judgment.
def _classify_url(
    domain: str,
    path: str,
    title_and_snippet: str,
) -> CulturalReferenceType:
    """Classify direct posts, media pages, articles, and ambiguous pages."""

    if "/r/tipofmytongue/" in path or is_obvious_informational_page(
        domain, path, title_and_snippet
    ):
        return CulturalReferenceType.INFORMATIONAL_ARTICLE
    if domain.endswith("tiktok.com") and "/video/" in path:
        return CulturalReferenceType.TIKTOK
    if domain.endswith("instagram.com") and (
        "/reel/" in path or "/p/" in path
    ):
        return CulturalReferenceType.INSTAGRAM_REEL
    if (domain.endswith("youtube.com") and "/shorts/" in path) or domain == "youtu.be":
        return CulturalReferenceType.VIRAL_VIDEO
    if domain.endswith("giphy.com") and (
        "/gifs/" in path or "/clips/" in path
    ):
        return CulturalReferenceType.GIF
    if domain.endswith("tenor.com") and "/view/" in path:
        return CulturalReferenceType.GIF
    if domain.endswith("knowyourmeme.com") and "/memes/" in path:
        return CulturalReferenceType.REACTION_MEME
    if domain.endswith("reddit.com") and "/comments/" in path:
        if any(marker in title_and_snippet for marker in ARTIFACT_QUERY_MARKERS):
            return CulturalReferenceType.REACTION_MEME
        return CulturalReferenceType.OTHER
    if domain.endswith("facebook.com") and "/videos/" in path:
        return CulturalReferenceType.VIRAL_VIDEO
    if "insidermemes.com" in domain and "/memes/template/" in path:
        return CulturalReferenceType.REACTION_MEME
    if domain.endswith("memix.com") and "/memix/" in path:
        return CulturalReferenceType.REACTION_MEME
    if domain.endswith("pinterest.com") and "/pin/" in path:
        return CulturalReferenceType.REACTION_MEME
    if domain.endswith("imgur.com") and (
        "/gallery/" in path or "/a/" in path
    ):
        return CulturalReferenceType.REACTION_MEME
    if domain.endswith("reactiongifs.com") and path.strip("/"):
        return CulturalReferenceType.GIF
    if domain.endswith("instagram.com"):
        return CulturalReferenceType.INFORMATIONAL_ARTICLE
    if domain.endswith("getyarn.io"):
        return CulturalReferenceType.FILM_TV_MOMENT
    if domain.endswith("youtube.com") and path == "/watch":
        if "anime" in title_and_snippet:
            return CulturalReferenceType.ANIME_MOMENT
        return CulturalReferenceType.FILM_TV_MOMENT
    return CulturalReferenceType.OTHER


# Reject recognizable news, advice, blog, and SEO patterns before model ranking.
def is_obvious_informational_page(
    domain: str,
    path: str,
    title_and_snippet: str,
) -> bool:
    """Return whether source evidence identifies a generic informational page."""

    if domain in ARTICLE_DOMAINS or any(
        domain.endswith(f".{blocked}") for blocked in ARTICLE_DOMAINS
    ):
        return True
    if domain.endswith(".edu"):
        return True
    if any(marker in path for marker in ARTICLE_PATH_MARKERS):
        return True
    return any(marker in title_and_snippet for marker in ARTICLE_TEXT_MARKERS)


# Separate obvious informational pages from candidates eligible for enrichment.
def filter_informational_candidates(
    candidates: Sequence[CulturalReferenceCandidate],
) -> tuple[list[CulturalReferenceCandidate], int]:
    """Discard informational articles and return the number rejected."""

    accepted: list[CulturalReferenceCandidate] = []
    for candidate in candidates:
        classified = classify_candidate(candidate)
        if (
            classified.cultural_reference_type
            != CulturalReferenceType.INFORMATIONAL_ARTICLE
        ):
            accepted.append(classified)
    return accepted, len(candidates) - len(accepted)


# Count only direct, traceable artifacts when deciding whether fallback is needed.
def count_direct_artifacts(candidates: Sequence[CulturalReferenceCandidate]) -> int:
    """Return the number of candidates with deterministic direct-artifact evidence."""

    return sum(
        classify_candidate(candidate).cultural_reference_type in DIRECT_ARTIFACT_TYPES
        for candidate in candidates
    )


# Reserve paid extraction for ambiguous pages with page-level artifact evidence.
def is_promising_ambiguous_candidate(
    candidate: CulturalReferenceCandidate,
) -> bool:
    """Return whether an unknown page title or excerpt indicates visual media."""

    classified = classify_candidate(candidate)
    if classified.cultural_reference_type != CulturalReferenceType.OTHER:
        return False
    page_text = f"{classified.title} {classified.snippet}".casefold()
    return any(marker in page_text for marker in ARTIFACT_QUERY_MARKERS)


# Put direct artifacts ahead of ambiguous pages before bounded Gemini evaluation.
def prioritize_artifacts(
    candidates: Sequence[CulturalReferenceCandidate],
) -> list[CulturalReferenceCandidate]:
    """Return direct artifacts first while preserving order within each tier."""

    classified = [classify_candidate(candidate) for candidate in candidates]
    return sorted(
        classified,
        key=lambda candidate: (
            candidate.cultural_reference_type == CulturalReferenceType.OTHER,
        ),
    )

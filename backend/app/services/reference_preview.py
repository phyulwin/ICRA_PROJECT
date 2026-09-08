# backend/app/services/reference_preview.py
"""Resolve safe preview images for verified direct cultural-reference pages."""

from collections.abc import Callable, Sequence
from functools import lru_cache
from html.parser import HTMLParser
from ipaddress import ip_address
from urllib.parse import urljoin, urlsplit

import httpx

from backend.app.schemas.reference import CulturalReferenceCandidate, RankedReference


# Limit server-side page fetches to established artifact platforms.
TRUSTED_PREVIEW_DOMAINS = {
    "facebook.com",
    "getyarn.io",
    "giphy.com",
    "imgur.com",
    "instagram.com",
    "insidermemes.com",
    "knowyourmeme.com",
    "memix.com",
    "pinterest.com",
    "reactiongifs.com",
    "tenor.com",
    "tiktok.com",
}

PREVIEW_META_KEYS = {
    "og:image",
    "og:image:secure_url",
    "twitter:image",
    "twitter:image:src",
}


# Read only social-preview metadata from a source page's HTML head.
class PreviewMetadataParser(HTMLParser):
    """Capture the first Open Graph or Twitter image URL."""

    def __init__(self) -> None:
        """Initialize parser state without retaining full page content."""

        super().__init__(convert_charrefs=True)
        self.image_url: str | None = None

    # Inspect metadata tags until one supported preview image is found.
    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        """Capture a supported metadata content attribute."""

        if self.image_url is not None or tag.casefold() != "meta":
            return
        attributes = {
            key.casefold(): value
            for key, value in attrs
            if value is not None
        }
        meta_key = (
            attributes.get("property", "") or attributes.get("name", "")
        ).casefold()
        content = attributes.get("content", "").strip()
        if meta_key in PREVIEW_META_KEYS and content:
            self.image_url = content


# Add source-provided thumbnails to ranked references without fabricating imagery.
class ReferencePreviewResolver:
    """Resolve trusted source metadata previews with safe fallback."""

    def __init__(
        self,
        fetch_html: Callable[[str], str | None] | None = None,
    ) -> None:
        """Accept an injectable HTML fetcher for deterministic tests."""

        self._fetch_html = fetch_html or fetch_trusted_html

    # Enrich the bounded ranked collection after all quality gates have passed.
    def enrich_ranked_references(
        self,
        references: Sequence[RankedReference],
    ) -> list[RankedReference]:
        """Return ranked references with available source preview URLs attached."""

        return [
            reference.model_copy(
                update={
                    "reference": self.enrich_candidate(reference.reference),
                }
            )
            for reference in references
        ]

    # Resolve one candidate while preserving null when no reliable preview exists.
    def enrich_candidate(
        self,
        candidate: CulturalReferenceCandidate,
    ) -> CulturalReferenceCandidate:
        """Attach a validated public preview URL to one source candidate."""

        if candidate.image_url is not None:
            return candidate
        source_url = str(candidate.url)
        preview_url = None
        if is_trusted_source_url(source_url):
            try:
                html = self._fetch_html(source_url)
                preview_url = parse_preview_url(html, source_url) if html else None
            except (httpx.HTTPError, UnicodeError, ValueError, TypeError):
                preview_url = None
        if preview_url is None or not is_public_image_url(preview_url):
            return candidate
        payload = candidate.model_dump(mode="python")
        payload["image_url"] = preview_url
        return CulturalReferenceCandidate.model_validate(payload)


# Parse social metadata and resolve relative image links against the source page.
def parse_preview_url(html: str, source_url: str) -> str | None:
    """Return one absolute Open Graph or Twitter preview image URL."""

    parser = PreviewMetadataParser()
    parser.feed(html)
    return urljoin(source_url, parser.image_url) if parser.image_url else None


# Reject untrusted hosts before issuing any server-side page request.
def is_trusted_source_url(url: str) -> bool:
    """Return whether the source URL belongs to an approved artifact platform."""

    parsed = urlsplit(url)
    domain = (parsed.hostname or "").casefold().removeprefix("www.")
    return parsed.scheme in {"http", "https"} and any(
        domain == trusted or domain.endswith(f".{trusted}")
        for trusted in TRUSTED_PREVIEW_DOMAINS
    )


# Validate metadata image URLs before returning them to the browser.
def is_public_image_url(url: str) -> bool:
    """Return whether a preview is a normal public HTTP image URL."""

    parsed = urlsplit(url)
    domain = (parsed.hostname or "").casefold()
    if (
        parsed.scheme not in {"http", "https"}
        or not domain
        or domain == "localhost"
        or domain.endswith(".local")
    ):
        return False
    try:
        return ip_address(domain.strip("[]")).is_global
    except ValueError:
        return True


# Fetch a bounded HTML prefix while validating every redirect target.
@lru_cache(maxsize=256)
def fetch_trusted_html(source_url: str) -> str | None:
    """Return up to 512 KB of trusted source HTML for metadata extraction."""

    current_url = source_url
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; CulturalReferenceDirector/1.0)",
        "Accept": "text/html,application/xhtml+xml",
    }
    try:
        with httpx.Client(timeout=5.0, follow_redirects=False, headers=headers) as client:
            for _ in range(4):
                if not is_trusted_source_url(current_url):
                    return None
                with client.stream("GET", current_url) as response:
                    if response.is_redirect:
                        location = response.headers.get("location")
                        if not location:
                            return None
                        current_url = urljoin(current_url, location)
                        continue
                    response.raise_for_status()
                    content_type = response.headers.get("content-type", "").casefold()
                    if "text/html" not in content_type:
                        return None
                    content = bytearray()
                    for chunk in response.iter_bytes():
                        remaining = 524288 - len(content)
                        if remaining <= 0:
                            break
                        content.extend(chunk[:remaining])
                    return bytes(content).decode(
                        response.encoding or "utf-8",
                        errors="replace",
                    )
    except (httpx.HTTPError, UnicodeError, ValueError):
        return None
    return None

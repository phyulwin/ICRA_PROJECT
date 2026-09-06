# backend/app/services/document_processor.py
"""Screenplay ingestion, text extraction, and deterministic scene parsing."""

from io import BytesIO
from pathlib import Path
import re
import os
from collections.abc import Callable

from google import genai
from google.genai import types
from pydantic import ValidationError
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from backend.app.schemas.scene import (
    DocumentProcessingResult,
    ExtractedDocumentText,
    Scene,
)
from backend.app.services.gemini_client import create_gemini_client
from backend.app.services.gemini_safety import GEMINI_SAFETY_SETTINGS


# Expose domain-specific exceptions so the API can return clear client errors.
class DocumentProcessingError(ValueError):
    """Raised when an uploaded screenplay cannot be safely processed."""


# Separate upstream model failures from malformed client document errors.
class NativeDocumentExtractionError(RuntimeError):
    """Raised when Gemini cannot recover text from a valid image-based PDF."""


# Adapt Google's native PDF Part pattern as a fallback for image-based screenplays.
class GeminiDocumentTextExtractor:
    """Recover screenplay text from a PDF that lacks an embedded text layer."""

    SYSTEM_INSTRUCTION = """You are a faithful screenplay transcription service.
Transcribe the complete supplied PDF in reading order. Preserve scene headings, line
breaks, character cues, dialogue, parentheticals, and action text. Do not summarize,
analyze, correct, or invent content. Return only the requested structured response."""

    # Accept an injected client so native document handling can be tested offline.
    def __init__(
        self,
        client: genai.Client | None = None,
        model_name: str | None = None,
        client_factory: Callable[[], genai.Client] = create_gemini_client,
    ) -> None:
        """Initialize native PDF extraction while deferring credentials until use."""

        self._client = client
        self._client_factory = client_factory
        self.model_name = model_name or os.getenv(
            "GOOGLE_GENAI_MODEL", "gemini-2.5-flash"
        )

    # Send the original PDF bytes with an explicit MIME type and typed response schema.
    def extract(self, content: bytes) -> str:
        """Return screenplay text extracted natively by Gemini from PDF bytes."""

        try:
            response = self._get_client().models.generate_content(
                model=self.model_name,
                contents=[
                    "Transcribe this screenplay PDF without changing its structure.",
                    types.Part.from_bytes(data=content, mime_type="application/pdf"),
                ],
                config=types.GenerateContentConfig(
                    system_instruction=self.SYSTEM_INSTRUCTION,
                    response_mime_type="application/json",
                    response_schema=ExtractedDocumentText,
                    safety_settings=GEMINI_SAFETY_SETTINGS,
                    temperature=0.0,
                ),
            )
            extracted = (
                ExtractedDocumentText.model_validate(response.parsed)
                if response.parsed is not None
                else ExtractedDocumentText.model_validate_json(response.text)
            )
            return extracted.text
        except (ValidationError, ValueError, TypeError, AttributeError) as exc:
            raise NativeDocumentExtractionError(
                "Gemini returned invalid structured document text."
            ) from exc
        except Exception as exc:
            raise NativeDocumentExtractionError(
                f"Gemini native PDF extraction failed: {exc}"
            ) from exc

    # Create the external client only when a scanned PDF requires it.
    def _get_client(self) -> genai.Client:
        """Return the configured Gemini client, creating it when required."""

        if self._client is None:
            self._client = self._client_factory()
        return self._client


# Centralize the production document-processing workflow.
class DocumentProcessor:
    """Validate screenplay uploads, extract text, and divide it into scenes."""

    SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".fountain"}
    MEDIA_TYPES = {
        ".pdf": "application/pdf",
        ".txt": "text/plain",
        ".fountain": "text/plain",
    }
    MAX_FILE_SIZE = 20 * 1024 * 1024
    MAX_PDF_PAGES = 300
    MAX_EXTRACTED_CHARACTERS = 2_000_000
    ACCEPTED_DECLARED_TYPES = {
        ".pdf": {"application/pdf", "application/octet-stream"},
        ".txt": {"text/plain", "application/octet-stream"},
        ".fountain": {
            "text/plain",
            "application/octet-stream",
            "application/x-fountain",
        },
    }
    SCENE_HEADING = re.compile(
        r"^\s*\.?((?:INT|EXT|INT/EXT|EXT/INT|I/E)\.)\s+(.+?)\s*$",
        re.IGNORECASE,
    )
    CHARACTER_CUE = re.compile(
        r"^([A-Z][A-Z0-9 .'\-]{0,38}?)(?:\s+\((?:V\.O\.|O\.S\.|CONT'D)\))?$"
    )
    TIMES_OF_DAY = {
        "DAY",
        "NIGHT",
        "MORNING",
        "AFTERNOON",
        "EVENING",
        "DAWN",
        "DUSK",
        "SUNRISE",
        "SUNSET",
        "LATER",
        "CONTINUOUS",
        "SAME TIME",
        "MOMENTS LATER",
    }

    # Keep ordinary parsing deterministic while allowing an optional native fallback.
    def __init__(
        self,
        native_pdf_extractor: Callable[[bytes], str] | None = None,
    ) -> None:
        """Configure optional Gemini extraction for PDFs without a text layer."""

        self._native_pdf_extractor = native_pdf_extractor

    # Validate bytes before dispatching to the appropriate extractor.
    def process_upload(
        self,
        filename: str,
        content: bytes,
        declared_media_type: str | None = None,
    ) -> DocumentProcessingResult:
        """Process an uploaded screenplay into structured scene objects."""

        safe_filename = Path(filename.replace("\\", "/")).name
        extension = Path(safe_filename).suffix.lower()
        if extension not in self.SUPPORTED_EXTENSIONS:
            raise DocumentProcessingError(
                "Unsupported file type. Upload a .pdf, .txt, or .fountain screenplay."
            )
        if not content:
            raise DocumentProcessingError("The uploaded screenplay is empty.")
        if len(content) > self.MAX_FILE_SIZE:
            raise DocumentProcessingError("The uploaded screenplay exceeds 20 MB.")

        normalized_media_type = (declared_media_type or "").split(";", 1)[0].lower()
        if (
            normalized_media_type
            and normalized_media_type not in self.ACCEPTED_DECLARED_TYPES[extension]
        ):
            raise DocumentProcessingError(
                "The uploaded MIME type does not match the screenplay extension."
            )
        if extension != ".pdf" and content.lstrip().startswith(b"%PDF-"):
            raise DocumentProcessingError(
                "The uploaded file signature does not match its extension."
            )
        if extension != ".pdf" and b"\x00" in content[:4096]:
            raise DocumentProcessingError("The screenplay text file appears to be binary.")

        text = self._extract_pdf(content) if extension == ".pdf" else self._decode_text(content)
        if len(text) > self.MAX_EXTRACTED_CHARACTERS:
            raise DocumentProcessingError(
                "The extracted screenplay exceeds the supported text length."
            )
        scenes = self.process_text(text)
        return DocumentProcessingResult(
            filename=safe_filename,
            media_type=self.MEDIA_TYPES[extension],
            character_count=len(text),
            scenes=scenes,
        )

    # Parse pasted text through the same scene detection logic as uploaded files.
    def process_text(self, text: str) -> list[Scene]:
        """Normalize screenplay text and split it at screenplay scene headings."""

        normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
        if not normalized:
            raise DocumentProcessingError("The screenplay contains no extractable text.")

        lines = normalized.split("\n")
        scene_starts = [
            index for index, line in enumerate(lines) if self._match_heading(line)
        ]
        if not scene_starts:
            return [self._build_scene(1, "UNTITLED SCENE", normalized)]

        scenes: list[Scene] = []
        for scene_number, start in enumerate(scene_starts, start=1):
            end = (
                scene_starts[scene_number]
                if scene_number < len(scene_starts)
                else len(lines)
            )
            raw_text = "\n".join(lines[start:end]).strip()
            scenes.append(self._build_scene(scene_number, lines[start].strip(), raw_text))
        return scenes

    # Extract embedded PDF text locally while retaining page and line boundaries.
    def _extract_pdf(self, content: bytes) -> str:
        """Extract text from a text-based PDF screenplay."""

        if not content.lstrip()[:5] == b"%PDF-":
            raise DocumentProcessingError("The PDF is malformed or unreadable.")

        try:
            reader = PdfReader(BytesIO(content))
            if reader.is_encrypted and reader.decrypt("") == 0:
                raise DocumentProcessingError("Password-protected PDFs are not supported.")
            if len(reader.pages) > self.MAX_PDF_PAGES:
                raise DocumentProcessingError("The PDF exceeds 300 pages.")
            pages = [(page.extract_text() or "").strip() for page in reader.pages]
        except DocumentProcessingError:
            raise
        except (PdfReadError, OSError, ValueError) as exc:
            raise DocumentProcessingError("The PDF is malformed or unreadable.") from exc

        text = "\n\n".join(page for page in pages if page)
        if not text.strip():
            if self._native_pdf_extractor is not None:
                recovered_text = self._native_pdf_extractor(content)
                if recovered_text.strip():
                    return recovered_text
            raise DocumentProcessingError(
                "The PDF contains no text that could be extracted."
            )
        return text

    # Decode conventional screenplay text files without silently losing characters.
    def _decode_text(self, content: bytes) -> str:
        """Decode UTF-8 or legacy Windows screenplay text bytes."""

        for encoding in ("utf-8-sig", "cp1252"):
            try:
                return content.decode(encoding)
            except UnicodeDecodeError:
                continue
        raise DocumentProcessingError("The screenplay text encoding is unsupported.")

    # Match standard and Fountain-forced scene headings.
    def _match_heading(self, line: str) -> re.Match[str] | None:
        """Return heading components when a line is a screenplay slug line."""

        return self.SCENE_HEADING.match(line)

    # Convert one scene block into its public schema.
    def _build_scene(self, scene_number: int, heading: str, raw_text: str) -> Scene:
        """Build a scene with parsed location, time, and character cues."""

        location, time_of_day = self._parse_heading(heading)
        return Scene(
            scene_id=f"scene_{scene_number:03d}",
            heading=heading.lstrip(".").strip(),
            location=location,
            time_of_day=time_of_day,
            characters=self._extract_characters(raw_text),
            raw_text=raw_text,
        )

    # Parse the final dash segment as time only when it follows screenplay convention.
    def _parse_heading(self, heading: str) -> tuple[str, str | None]:
        """Separate a slug line into location and time-of-day fields."""

        match = self._match_heading(heading)
        if not match:
            return heading, None

        body = match.group(2).strip()
        segments = [segment.strip() for segment in body.split(" - ")]
        possible_time = segments[-1].upper()
        if len(segments) > 1 and possible_time in self.TIMES_OF_DAY:
            return " - ".join(segments[:-1]), segments[-1]
        return body, None

    # Identify conventional uppercase dialogue cues and preserve first appearance order.
    def _extract_characters(self, raw_text: str) -> list[str]:
        """Extract likely character names from screenplay dialogue cues."""

        lines = raw_text.split("\n")
        characters: list[str] = []
        for index, line in enumerate(lines):
            candidate = line.strip()
            match = self.CHARACTER_CUE.fullmatch(candidate)
            if (
                not match
                or self._match_heading(candidate)
                or candidate.endswith(("TO:", ".", "!", "?"))
            ):
                continue
            following_lines = [value.strip() for value in lines[index + 1 :] if value.strip()]
            if not following_lines or len(candidate.split()) > 4:
                continue
            name = match.group(1).strip()
            if name not in characters:
                characters.append(name)
        return characters

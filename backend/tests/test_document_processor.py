# backend/tests/test_document_processor.py
"""Tests for pasted, text-file, PDF, and malformed screenplay ingestion."""

from types import SimpleNamespace

from backend.app.schemas.scene import ExtractedDocumentText
from backend.app.services.document_processor import (
    DocumentProcessingError,
    DocumentProcessor,
    GeminiDocumentTextExtractor,
)


# Simulate Gemini's document model surface and retain the native PDF request.
class FakeDocumentModels:
    """Return a screenplay transcription for a PDF without a text layer."""

    def __init__(self) -> None:
        """Initialize request capture state."""

        self.last_request: dict[str, object] = {}

    def generate_content(self, **kwargs: object) -> SimpleNamespace:
        """Capture the request and return structured extracted screenplay text."""

        self.last_request = kwargs
        return SimpleNamespace(
            parsed={"text": "EXT. PLATFORM - NIGHT\n\nMAYA\nThe last train."},
            text="",
        )


# Match the production SDK client's models attribute for isolated tests.
class FakeDocumentClient:
    """Minimal Gemini client used for native PDF extraction tests."""

    def __init__(self) -> None:
        """Expose the fake document models service."""

        self.models = FakeDocumentModels()


# Build a compact standards-compliant PDF fixture without adding a test-only library.
def build_text_pdf(lines: list[str]) -> bytes:
    """Create a one-page PDF whose text can be extracted by pypdf."""

    escaped_lines = [
        line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        for line in lines
    ]
    commands = ["BT", "/F1 12 Tf", "14 TL", "72 720 Td"]
    for index, line in enumerate(escaped_lines):
        if index:
            commands.append("T*")
        commands.append(f"({line}) Tj")
    commands.append("ET")
    stream = "\n".join(commands).encode("ascii")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Length {len(stream)} >>\nstream\n".encode("ascii")
        + stream
        + b"\nendstream",
    ]

    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for object_number, body in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{object_number} 0 obj\n".encode("ascii"))
        pdf.extend(body)
        pdf.extend(b"\nendobj\n")

    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n".encode("ascii")
    )
    return bytes(pdf)


# Confirm pasted screenplay parsing preserves headings and dialogue structure.
def test_pasted_scene_is_structured() -> None:
    """Parse one pasted screenplay scene into all required fields."""

    processor = DocumentProcessor()
    scenes = processor.process_text(
        "INT. APARTMENT - NIGHT\n\nJOHN\nI did not eat the cake.\n\n"
        "Everyone notices frosting on his shirt."
    )

    assert len(scenes) == 1
    assert scenes[0].scene_id == "scene_001"
    assert scenes[0].location == "APARTMENT"
    assert scenes[0].time_of_day == "NIGHT"
    assert scenes[0].characters == ["JOHN"]
    assert scenes[0].raw_text.startswith("INT. APARTMENT")


# Confirm ordinary UTF-8 text uploads divide multiple scenes in order.
def test_txt_upload_extracts_multiple_scenes() -> None:
    """Process a .txt upload containing two screenplay scenes."""

    processor = DocumentProcessor()
    result = processor.process_upload(
        "sample.txt",
        b"EXT. PARK - DAY\n\nMAYA\nRun!\n\nINT. CAR - NIGHT\n\nLEO\nDrive!",
    )

    assert result.media_type == "text/plain"
    assert [scene.location for scene in result.scenes] == ["PARK", "CAR"]
    assert result.scenes[1].characters == ["LEO"]


# Confirm Fountain's forced-heading marker is accepted and removed from the heading.
def test_fountain_upload_extracts_forced_scene_heading() -> None:
    """Process a .fountain upload using a forced scene heading."""

    processor = DocumentProcessor()
    result = processor.process_upload(
        "sample.fountain",
        b".INT. ARCHIVE - NIGHT\n\nELENA\nWe keep the originals.",
    )

    assert result.media_type == "text/plain"
    assert result.scenes[0].heading == "INT. ARCHIVE - NIGHT"
    assert result.scenes[0].location == "ARCHIVE"
    assert result.scenes[0].characters == ["ELENA"]


# Confirm a real text-based PDF passes through pypdf and scene extraction.
def test_pdf_upload_extracts_scene() -> None:
    """Process a valid PDF screenplay fixture end to end."""

    processor = DocumentProcessor()
    pdf = build_text_pdf(["INT. KITCHEN - MORNING", "ANNA", "Coffee?"])
    result = processor.process_upload("sample.pdf", pdf)

    assert result.media_type == "application/pdf"
    assert len(result.scenes) == 1
    assert result.scenes[0].location == "KITCHEN"
    assert result.scenes[0].characters == ["ANNA"]


# Confirm valid image-based PDFs use Gemini's native document Part as a fallback only.
def test_pdf_without_text_uses_native_gemini_fallback() -> None:
    """Recover screenplay text from a valid PDF with no embedded text."""

    client = FakeDocumentClient()
    extractor = GeminiDocumentTextExtractor(client=client, model_name="test-model")
    processor = DocumentProcessor(native_pdf_extractor=extractor.extract)

    result = processor.process_upload("scan.pdf", build_text_pdf([]))

    assert result.scenes[0].location == "PLATFORM"
    request = client.models.last_request
    assert request["model"] == "test-model"
    assert request["config"].response_schema is ExtractedDocumentText
    assert request["contents"][1].inline_data.mime_type == "application/pdf"


# Confirm unsupported and malformed inputs fail with domain-level errors.
def test_unsupported_and_malformed_inputs() -> None:
    """Reject unsupported extensions, empty content, and invalid PDF bytes."""

    processor = DocumentProcessor()

    for filename, content in (
        ("script.docx", b"content"),
        ("script.txt", b""),
        ("script.pdf", b"not a pdf"),
    ):
        try:
            processor.process_upload(filename, content)
        except DocumentProcessingError:
            continue
        raise AssertionError(f"Expected {filename} to be rejected")

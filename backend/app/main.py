# backend/app/main.py
"""FastAPI entry point for Cultural Reference Director Phase 2."""

import json
import os

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pydantic import ValidationError
from dotenv import load_dotenv

from backend.app.agents.script_analyzer import (
    ScriptAnalysisError,
    ScriptIntelligenceAgent,
)
from backend.app.agents.reference_ranker import ReferenceRankingError
from backend.app.schemas.reference import (
    ReferenceSearchRequest,
    ReferenceSearchResponse,
)
from backend.app.schemas.scene import (
    AnalyzedScene,
    DocumentProcessingResult,
    MultimodalAnalysisResult,
    PastedScreenplayRequest,
    Scene,
    ScreenplayAnalysisResult,
)
from backend.app.services.document_processor import (
    DocumentProcessingError,
    DocumentProcessor,
    GeminiDocumentTextExtractor,
    NativeDocumentExtractionError,
)
from backend.app.services.multimodal_analyzer import (
    MultimodalAnalysisError,
    MultimodalAnalyzer,
)
from backend.app.services.reference_service import ReferenceDiscoveryService
from backend.app.tools.parallel_search import (
    ParallelConfigurationError,
    ParallelSearchError,
)

# Load local development settings before establishing the browser origin allowlist.
load_dotenv()
app = FastAPI(title="ICRA Backend", version="0.1.0")
frontend_origins = [
    origin.strip()
    for origin in os.getenv("FRONTEND_ORIGINS", "http://localhost:3000").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=frontend_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)


# Construct stateless services once; Gemini clients remain lazy until first use.
gemini_document_extractor = GeminiDocumentTextExtractor()
document_processor = DocumentProcessor(
    native_pdf_extractor=gemini_document_extractor.extract
)
script_intelligence_agent = ScriptIntelligenceAgent()
multimodal_analyzer = MultimodalAnalyzer()
reference_discovery_service = ReferenceDiscoveryService()


class HealthResponse(BaseModel):
    """Stable service-health response contract."""

    status: str
    service: str


@app.get("/health", response_model=HealthResponse)
def healthcheck() -> HealthResponse:
    """Report API availability without requiring Google Cloud credentials."""

    return {"status": "ok", "service": "icra-backend"}


@app.get("/")
def read_root() -> dict[str, str]:
    """Return a concise API landing response."""

    return {"message": "ICRA API is running"}


# Provide deterministic parsing independently of Gemini for previews and validation.
@app.post("/api/v1/screenplays/parse", response_model=DocumentProcessingResult)
async def parse_screenplay(file: UploadFile = File(...)) -> DocumentProcessingResult:
    """Validate and parse an uploaded PDF, text, or Fountain screenplay."""

    content = await file.read()
    try:
        return document_processor.process_upload(file.filename or "screenplay.txt", content)
    except DocumentProcessingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except NativeDocumentExtractionError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


# Execute the complete Phase 2 upload-to-structured-intelligence workflow.
@app.post("/api/v1/screenplays/analyze", response_model=ScreenplayAnalysisResult)
async def analyze_screenplay(file: UploadFile = File(...)) -> ScreenplayAnalysisResult:
    """Parse an uploaded screenplay and analyze every extracted scene with Gemini."""

    document = await parse_screenplay(file)
    try:
        analyses = await run_in_threadpool(
            script_intelligence_agent.analyze_scenes, document.scenes
        )
    except ScriptAnalysisError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return ScreenplayAnalysisResult(
        filename=document.filename,
        media_type=document.media_type,
        character_count=document.character_count,
        scenes=[
            AnalyzedScene(scene=scene, analysis=analysis)
            for scene, analysis in zip(document.scenes, analyses, strict=True)
        ],
    )


# Support pasted scenes through the same ingestion and Gemini pipeline.
@app.post("/api/v1/screenplays/analyze-text", response_model=ScreenplayAnalysisResult)
async def analyze_pasted_screenplay(
    request: PastedScreenplayRequest,
) -> ScreenplayAnalysisResult:
    """Analyze screenplay content pasted directly into the application."""

    try:
        document = document_processor.process_upload(
            request.filename, request.text.encode("utf-8")
        )
        analyses = await run_in_threadpool(
            script_intelligence_agent.analyze_scenes, document.scenes
        )
    except DocumentProcessingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ScriptAnalysisError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return ScreenplayAnalysisResult(
        filename=document.filename,
        media_type=document.media_type,
        character_count=document.character_count,
        scenes=[
            AnalyzedScene(scene=scene, analysis=analysis)
            for scene, analysis in zip(document.scenes, analyses, strict=True)
        ],
    )


# Analyze an image or video reference against a client-selected screenplay scene.
@app.post(
    "/api/v1/scenes/multimodal-analyze", response_model=MultimodalAnalysisResult
)
async def analyze_multimodal_reference(
    scene_json: str = Form(...),
    media: UploadFile = File(...),
) -> MultimodalAnalysisResult:
    """Return structured filmmaking observations for uploaded reference media."""

    try:
        scene = Scene.model_validate(json.loads(scene_json))
        content = await media.read()
        media_type = media.content_type or "application/octet-stream"
        analysis = await run_in_threadpool(
            multimodal_analyzer.analyze, scene, content, media_type
        )
    except (json.JSONDecodeError, ValidationError) as exc:
        raise HTTPException(status_code=400, detail="scene_json is invalid.") from exc
    except MultimodalAnalysisError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return MultimodalAnalysisResult(
        scene_id=scene.scene_id,
        media_type=media_type,
        analysis=analysis,
    )


# Execute real Parallel discovery against an existing Phase 2 scene analysis.
@app.post(
    "/api/v1/scenes/{scene_id}/references",
    response_model=ReferenceSearchResponse,
)
async def find_scene_references(
    scene_id: str,
    request: ReferenceSearchRequest,
) -> ReferenceSearchResponse:
    """Search and rank traceable cultural references without reanalyzing the scene."""

    if scene_id != request.scene.scene_id:
        raise HTTPException(
            status_code=400,
            detail="The route scene_id does not match the request scene.",
        )
    try:
        return await run_in_threadpool(
            reference_discovery_service.find_references,
            request,
        )
    except ParallelConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ParallelSearchError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except ReferenceRankingError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

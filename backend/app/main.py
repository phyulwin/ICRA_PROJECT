# backend/app/main.py
"""Production FastAPI entry point for Cultural Reference Director."""

import asyncio
import json
import os
import time
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError

from backend.app.agents.reference_ranker import ReferenceRankingError
from backend.app.agents.script_analyzer import ScriptAnalysisError, ScriptIntelligenceAgent
from backend.app.schemas.reference import ReferenceSearchRequest, ReferenceSearchResponse
from backend.app.schemas.scene import AnalyzedScene, DocumentProcessingResult, MultimodalAnalysisResult, PastedScreenplayRequest, Scene, ScreenplayAnalysisResult
from backend.app.services.agent_engine_service import AgentEngineGateway, AgentEngineInvocationError
from backend.app.services.document_processor import DocumentProcessingError, DocumentProcessor, GeminiDocumentTextExtractor, NativeDocumentExtractionError
from backend.app.services.multimodal_analyzer import MultimodalAnalysisError, MultimodalAnalyzer
from backend.app.services.reference_service import ReferenceDiscoveryService
from backend.app.services.structured_logging import configure_structured_logger, log_event
from backend.app.tools.parallel_search import ParallelConfigurationError, ParallelSearchError

# Load local-only settings while Cloud Run supplies production variables directly.
load_dotenv()
logger = configure_structured_logger("icra.api")
MAX_HTTP_REQUEST_BYTES = int(os.getenv("MAX_HTTP_REQUEST_BYTES", str(55 * 1024 * 1024)))
REQUEST_TIMEOUT_SECONDS = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "280"))

# Configure the public API without framework debug tracebacks.
app = FastAPI(title="ICRA Backend", version="1.0.0", debug=False)
frontend_origins = [origin.strip() for origin in os.getenv("FRONTEND_ORIGINS", "http://localhost:3000").split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=frontend_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
)


# Enforce request bounds and emit metadata-only structured logs.
@app.middleware("http")
async def request_controls(request: Request, call_next):
    """Attach request IDs, enforce size/time limits, and log safe metadata."""

    request_id = request.headers.get("X-Request-ID", str(uuid4()))[:128]
    request.state.request_id = request_id
    started = time.perf_counter()
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > MAX_HTTP_REQUEST_BYTES:
                return JSONResponse(status_code=413, content={"detail": "The request exceeds the maximum allowed size."}, headers={"X-Request-ID": request_id})
        except ValueError:
            return JSONResponse(status_code=400, content={"detail": "The Content-Length header is invalid."}, headers={"X-Request-ID": request_id})
    try:
        response = await asyncio.wait_for(call_next(request), timeout=REQUEST_TIMEOUT_SECONDS)
    except TimeoutError:
        response = JSONResponse(status_code=504, content={"detail": "The request timed out before completion."})
    except Exception:
        log_event(logger, "request_failed", request_id=request_id, route=request.url.path, error_category="unhandled")
        response = JSONResponse(status_code=500, content={"detail": "The service could not complete the request."})
    response.headers["X-Request-ID"] = request_id
    log_event(logger, "request_complete", request_id=request_id, route=request.url.path, method=request.method, status_code=response.status_code, latency_ms=round((time.perf_counter() - started) * 1000, 2))
    return response


# Construct stateless services once while external clients remain lazy.
gemini_document_extractor = GeminiDocumentTextExtractor()
document_processor = DocumentProcessor(native_pdf_extractor=gemini_document_extractor.extract)
script_intelligence_agent = ScriptIntelligenceAgent()
multimodal_analyzer = MultimodalAnalyzer()
reference_discovery_service = ReferenceDiscoveryService()
agent_engine_gateway = AgentEngineGateway()


# Define lightweight health contracts that never reveal configuration values.
class HealthResponse(BaseModel):
    """Stable service-health response contract."""

    status: str
    service: str


class ReadinessResponse(HealthResponse):
    """Readiness response with names of missing settings only."""

    missing_configuration: list[str] = []


# Read upload streams incrementally so oversized bodies are rejected promptly.
async def _read_upload(upload: UploadFile, limit: int) -> bytes:
    """Read an upload in bounded chunks and reject content over its domain limit."""

    content = bytearray()
    try:
        while chunk := await upload.read(1024 * 1024):
            content.extend(chunk)
            if len(content) > limit:
                raise HTTPException(status_code=413, detail="The uploaded file exceeds the allowed size.")
        return bytes(content)
    finally:
        await upload.close()


# Keep upload parsing in one boundary shared by parsing and analysis routes.
async def _parse_uploaded_screenplay(file: UploadFile) -> DocumentProcessingResult:
    """Validate, extract, and parse one bounded screenplay upload."""

    content = await _read_upload(file, DocumentProcessor.MAX_FILE_SIZE)
    return await run_in_threadpool(document_processor.process_upload, file.filename or "screenplay.txt", content, file.content_type)


# Analyze through Agent Engine in production and preserve local development behavior.
async def _analyze_scenes(scenes: list[Scene]):
    """Analyze scenes through the configured managed or local boundary."""

    if agent_engine_gateway.enabled:
        analyses = []
        for scene in scenes:
            analyses.append(await agent_engine_gateway.analyze_scene(scene))
        return analyses
    return await run_in_threadpool(script_intelligence_agent.analyze_scenes, scenes)


@app.get("/health", response_model=HealthResponse)
def healthcheck() -> HealthResponse:
    """Report process liveness without calling paid upstream services."""

    return HealthResponse(status="ok", service="icra-backend")


@app.get("/ready", response_model=ReadinessResponse)
def readiness() -> ReadinessResponse | JSONResponse:
    """Verify required setting names without exposing their values."""

    required = ["GOOGLE_CLOUD_PROJECT", "PARALLEL_API_KEY"]
    if agent_engine_gateway.enabled:
        required.append("AGENT_ENGINE_RESOURCE_NAME")
    missing = [name for name in required if not os.getenv(name, "").strip()]
    payload = ReadinessResponse(status="ready" if not missing else "not_ready", service="icra-backend", missing_configuration=missing)
    if missing:
        return JSONResponse(status_code=503, content=payload.model_dump())
    return payload


@app.get("/")
def read_root() -> dict[str, str]:
    """Return a concise API landing response."""

    return {"message": "ICRA API is running"}


@app.post("/api/v1/screenplays/parse", response_model=DocumentProcessingResult)
async def parse_screenplay(file: UploadFile = File(...)) -> DocumentProcessingResult:
    """Validate and parse an uploaded PDF, text, or Fountain screenplay."""

    try:
        return await _parse_uploaded_screenplay(file)
    except DocumentProcessingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except NativeDocumentExtractionError as exc:
        raise HTTPException(status_code=502, detail="Document text extraction is temporarily unavailable.") from exc


@app.post("/api/v1/screenplays/analyze", response_model=ScreenplayAnalysisResult)
async def analyze_screenplay(file: UploadFile = File(...)) -> ScreenplayAnalysisResult:
    """Parse an uploaded screenplay and analyze every scene through Gemini."""

    try:
        document = await _parse_uploaded_screenplay(file)
        analyses = await _analyze_scenes(document.scenes)
    except DocumentProcessingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except NativeDocumentExtractionError as exc:
        raise HTTPException(status_code=502, detail="Document text extraction is temporarily unavailable.") from exc
    except (ScriptAnalysisError, AgentEngineInvocationError) as exc:
        raise HTTPException(status_code=getattr(exc, "status_code", 502), detail="Scene analysis is temporarily unavailable.") from exc
    return ScreenplayAnalysisResult(filename=document.filename, media_type=document.media_type, character_count=document.character_count, scenes=[AnalyzedScene(scene=scene, analysis=analysis) for scene, analysis in zip(document.scenes, analyses, strict=True)])


@app.post("/api/v1/screenplays/analyze-text", response_model=ScreenplayAnalysisResult)
async def analyze_pasted_screenplay(request: PastedScreenplayRequest) -> ScreenplayAnalysisResult:
    """Analyze pasted screenplay content through the same workflow."""

    try:
        document = await run_in_threadpool(document_processor.process_upload, request.filename, request.text.encode("utf-8"), "text/plain")
        analyses = await _analyze_scenes(document.scenes)
    except DocumentProcessingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (ScriptAnalysisError, AgentEngineInvocationError) as exc:
        raise HTTPException(status_code=getattr(exc, "status_code", 502), detail="Scene analysis is temporarily unavailable.") from exc
    return ScreenplayAnalysisResult(filename=document.filename, media_type=document.media_type, character_count=document.character_count, scenes=[AnalyzedScene(scene=scene, analysis=analysis) for scene, analysis in zip(document.scenes, analyses, strict=True)])


@app.post("/api/v1/scenes/multimodal-analyze", response_model=MultimodalAnalysisResult)
async def analyze_multimodal_reference(scene_json: str = Form(...), media: UploadFile = File(...)) -> MultimodalAnalysisResult:
    """Return validated filmmaking observations for uploaded reference media."""

    try:
        scene = Scene.model_validate(json.loads(scene_json))
        content = await _read_upload(media, MultimodalAnalyzer.MAX_MEDIA_SIZE)
        media_type = media.content_type or "application/octet-stream"
        analysis = await run_in_threadpool(multimodal_analyzer.analyze, scene, content, media_type)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise HTTPException(status_code=400, detail="scene_json is invalid.") from exc
    except MultimodalAnalysisError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return MultimodalAnalysisResult(scene_id=scene.scene_id, media_type=media_type, analysis=analysis)


@app.post("/api/v1/scenes/{scene_id}/references", response_model=ReferenceSearchResponse)
async def find_scene_references(scene_id: str, request: ReferenceSearchRequest) -> ReferenceSearchResponse:
    """Search and rank references through the configured ADK boundary."""

    if scene_id != request.scene.scene_id:
        raise HTTPException(status_code=400, detail="The route scene_id does not match the request scene.")
    try:
        if agent_engine_gateway.enabled:
            return await agent_engine_gateway.find_references(request)
        return await run_in_threadpool(reference_discovery_service.find_references, request)
    except ParallelConfigurationError as exc:
        raise HTTPException(status_code=503, detail="Reference search is not configured.") from exc
    except ParallelSearchError as exc:
        raise HTTPException(status_code=exc.status_code, detail="Reference search is temporarily unavailable.") from exc
    except (ReferenceRankingError, AgentEngineInvocationError) as exc:
        raise HTTPException(status_code=getattr(exc, "status_code", 502), detail="Reference ranking is temporarily unavailable.") from exc

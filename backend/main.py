import logging
import os
from contextlib import asynccontextmanager
from logging.handlers import RotatingFileHandler
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.models.schemas import ErrorResponse
from backend.routes import analyze, health
from backend.services.image_validator import MAX_SIZE_BYTES, TOO_LARGE_MESSAGE

# Console + a rotating file (logs/ is gitignored). The file makes provider
# errors diagnosable after the fact without scrolling a terminal.
_LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
_LOG_DIR.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        RotatingFileHandler(_LOG_DIR / "backend.log", maxBytes=2_000_000, backupCount=2, encoding="utf-8"),
    ],
)
logger = logging.getLogger("labelwise")



@asynccontextmanager
async def _lifespan(app: FastAPI):
    # Say which vision provider (if any) will answer, so a silent fallback
    # to keyword-only mode is obvious in the terminal from the first line.
    from backend.services import vision_classifier

    name = vision_classifier.provider()
    if name == "gemini":
        from backend.services.vision_providers import gemini
        logger.info("Vision: Gemini (%s)", gemini.MODEL_ID)
    elif name == "claude":
        from backend.services.vision_providers import claude
        logger.info("Vision: Claude (%s)", claude.MODEL_ID)
    else:
        logger.info("Vision: OFF — keyword-only mode (set GEMINI_API_KEY or ANTHROPIC_API_KEY)")
    yield


app = FastAPI(title="LabelWise API", lifespan=_lifespan)

# Comma-separated list of allowed origins. Defaults to the local Streamlit
# dev server; set LABELWISE_CORS_ORIGINS="*" only for a throwaway demo.
_origins = [o.strip() for o in os.environ.get("LABELWISE_CORS_ORIGINS", "http://localhost:8501").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

# Multipart overhead on top of the image itself (boundary, headers).
_MAX_REQUEST_BYTES = MAX_SIZE_BYTES + 64 * 1024


@app.middleware("http")
async def reject_oversized_uploads(request: Request, call_next):
    # Reject on the declared size BEFORE the body is parsed/spooled, so a
    # huge upload is refused up front instead of being received in full and
    # only then failing validation. The route's capped read handles clients
    # that lie about (or omit) Content-Length.
    if request.url.path == "/analyze" and request.method == "POST":
        declared = request.headers.get("content-length")
        if declared and declared.isdigit() and int(declared) > _MAX_REQUEST_BYTES:
            return JSONResponse(
                status_code=422,
                content=ErrorResponse(message=TOO_LARGE_MESSAGE).model_dump(),
            )
    return await call_next(request)


app.include_router(health.router)
app.include_router(analyze.router)


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    # Never leak tracebacks/internal errors to the client — log server-side,
    # return the exact PRD-defined generic message instead.
    logger.exception("Unhandled error on %s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "error": True,
            "message": "LabelWise couldn't complete the analysis. Please try again.",
        },
    )

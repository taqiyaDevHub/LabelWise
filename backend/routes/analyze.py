"""
POST /analyze — HTTP wrapper around services/pipeline.py.

This route only does transport: capped body read, then translate the
pipeline's exceptions into the {"error": true, "message": ...} contract.
The analysis logic itself lives in services/pipeline.py so the Streamlit
frontend can also run it in-process (single-app deploys) with identical
behavior.

response_model is intentionally NOT set on the route: error paths return the
separate {"error": true, "message": ...} shape, and FastAPI's response_model
validation would reject that. We return AnalysisResult or ErrorResponse
explicitly via JSONResponse instead.
"""

from typing import List

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import JSONResponse

from backend.models.schemas import ErrorResponse
from backend.services import pipeline
from backend.services.image_validator import MAX_SIZE_BYTES, TOO_LARGE_MESSAGE, ImageValidationError

router = APIRouter()

_READ_CHUNK = 256 * 1024


async def _read_capped(file: UploadFile, cap: int) -> bytes:
    """Read the upload without ever holding more than `cap` bytes — a
    too-large body is rejected as soon as it crosses the limit rather than
    being buffered in full first. (main.py also rejects on Content-Length
    before the body is parsed at all; this is the second line of defense.)"""
    chunks: List[bytes] = []
    total = 0
    while True:
        chunk = await file.read(_READ_CHUNK)
        if not chunk:
            break
        total += len(chunk)
        if total > cap:
            raise ImageValidationError(TOO_LARGE_MESSAGE)
        chunks.append(chunk)
    return b"".join(chunks)


def _error(message: str, status_code: int = 422) -> JSONResponse:
    return JSONResponse(status_code=status_code, content=ErrorResponse(message=message).model_dump())


@router.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    try:
        contents = await _read_capped(file, MAX_SIZE_BYTES)
        return pipeline.analyze_image(contents, file.filename, file.content_type)
    except ImageValidationError as e:
        return _error(e.message)
    except pipeline.AnalysisUncertain as e:
        # PRD FR-11: never invent a classification when unsure.
        return _error(e.message)

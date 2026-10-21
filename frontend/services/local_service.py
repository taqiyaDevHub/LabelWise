"""In-process implementation of AnalysisService — no HTTP, no second server.

Runs backend/services/pipeline.py directly inside the Streamlit process.
This is what makes a single-app deploy (Streamlit Community Cloud) possible:
the FastAPI server isn't needed, but the analysis code is byte-for-byte the
same one POST /analyze runs, so results are identical.

Select it with LABELWISE_ANALYSIS_MODE=local (see app.py).
"""

import mimetypes
import sys
from pathlib import Path
from typing import Optional

# `backend` is a sibling package of `frontend`; Streamlit only puts the
# script's own directory on sys.path, so add the repo root explicitly.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from models.result import AnalysisResult
from services.analysis_service import AnalysisError, AnalysisService

ERR_ANALYSIS_FAILURE = "LabelWise couldn't complete the analysis. Please try again."


class LocalAnalysisService(AnalysisService):
    """Calls the backend pipeline in-process."""

    def analyze_image(self, image_bytes: bytes, filename: str) -> AnalysisResult:
        from backend.services import pipeline
        from backend.services.image_validator import ImageValidationError

        content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        try:
            result = pipeline.analyze_image(image_bytes, filename, content_type)
        except (ImageValidationError, pipeline.AnalysisUncertain) as e:
            # Same exact PRD strings the HTTP route returns.
            raise AnalysisError(e.message)
        except Exception:
            # Mirror the API's global handler: never surface a traceback.
            raise AnalysisError(ERR_ANALYSIS_FAILURE)

        return AnalysisResult.from_dict(result.model_dump())

    def health(self) -> Optional[dict]:
        from backend.services import vision_classifier

        provider = vision_classifier.provider()
        return {"status": "ok", "vision_enabled": provider is not None, "vision_provider": provider}

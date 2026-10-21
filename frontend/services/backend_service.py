"""Real backend implementation of AnalysisService (Phase 9 / integration).

Talks to the LabelWise FastAPI backend's POST /analyze over HTTP. This is
the only new file needed to go from demo mode to a live backend — UI
components (app.py, results_dashboard.py) are untouched, per the contract
laid out in analysis_service.py.
"""

import mimetypes
import os
from typing import Optional

import requests

from models.result import AnalysisResult
from services.analysis_service import AnalysisError, AnalysisService

# Overridable via environment variable so the same code works locally, in a
# container, or wherever the backend ends up deployed for the demo, without
# a code change.
BACKEND_URL = os.environ.get("LABELWISE_BACKEND_URL", "http://localhost:8000")
ANALYZE_ENDPOINT = f"{BACKEND_URL.rstrip('/')}/analyze"
HEALTH_ENDPOINT = f"{BACKEND_URL.rstrip('/')}/health"

# PRD targets ~<15s AI analysis / ~<20s total experience; the vision model
# call can take most of that on a large photo, so leave real headroom rather
# than cutting the request off right at the target.
REQUEST_TIMEOUT_SECONDS = 60
HEALTH_TIMEOUT_SECONDS = 2

ERR_ANALYSIS_FAILURE = "LabelWise couldn't complete the analysis. Please try again."


class BackendAnalysisService(AnalysisService):
    """Calls the real LabelWise FastAPI backend's POST /analyze endpoint."""

    def analyze_image(self, image_bytes: bytes, filename: str) -> AnalysisResult:
        content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"

        try:
            response = requests.post(
                ANALYZE_ENDPOINT,
                files={"file": (filename, image_bytes, content_type)},
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        except requests.RequestException:
            # Network failure, timeout, connection refused, DNS error, etc.
            # — never expose the raw exception to the user.
            raise AnalysisError(ERR_ANALYSIS_FAILURE)

        try:
            data = response.json()
        except ValueError:
            # Backend returned something that isn't JSON at all (e.g. a
            # proxy error page). Still never a raw traceback to the user.
            raise AnalysisError(ERR_ANALYSIS_FAILURE)

        # Check the error contract BEFORE parsing as a canonical result.
        # Both success (200) and handled errors (422) come back as JSON —
        # only the error shape has "error": true. This works for the 500
        # fallback too, since the backend's global exception handler
        # returns the same {"error": true, "message": ...} shape.
        if isinstance(data, dict) and data.get("error") is True:
            raise AnalysisError(data.get("message", ERR_ANALYSIS_FAILURE))

        try:
            return AnalysisResult.from_dict(data)
        except (KeyError, TypeError):
            # Response didn't match the expected canonical shape — treat as
            # a failure rather than crashing the UI with a stack trace.
            raise AnalysisError(ERR_ANALYSIS_FAILURE)

    def health(self) -> Optional[dict]:
        try:
            response = requests.get(HEALTH_ENDPOINT, timeout=HEALTH_TIMEOUT_SECONDS)
            data = response.json()
        except (requests.RequestException, ValueError):
            return None
        return data if isinstance(data, dict) and data.get("status") == "ok" else None

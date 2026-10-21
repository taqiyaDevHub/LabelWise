"""Service layer interface for LabelWise image analysis.

This module defines the boundary between UI and analysis backend.
UI components must NEVER make HTTP requests directly — all backend
communication happens through implementations of AnalysisService:

- BackendAnalysisService (services/backend_service.py): real FastAPI backend
- MockAnalysisService   (services/mock_service.py):    demo data, no backend

Error contract: implementations raise AnalysisError with the exact
PRD-defined user-facing message. The UI displays it as-is.
Result contract: models/result.py mirrors backend/models/schemas.py.
"""

from abc import ABC, abstractmethod
from typing import Optional

from models.result import AnalysisResult


class AnalysisError(Exception):
    """Raised when analysis fails.

    The message attribute contains the exact PRD-defined user-facing error string.
    UI displays this message as-is — never modify or wrap it.
    """

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class AnalysisService(ABC):
    """Abstract interface for image analysis.

    Implementations:
    - MockAnalysisService: Demo/development (current)
    - BackendAnalysisService: Real backend HTTP calls (Phase 9)

    The UI only depends on this abstract interface.
    """

    @abstractmethod
    def analyze_image(self, image_bytes: bytes, filename: str) -> AnalysisResult:
        """Analyze an uploaded image.

        Args:
            image_bytes: Raw image file content
            filename: Original filename (used for demo triggers in mock)

        Returns:
            AnalysisResult with canonical 7-field structure

        Raises:
            AnalysisError: With exact PRD-defined message on failure
        """
        pass

    def health(self) -> Optional[dict]:
        """Backend status, e.g. {"status": "ok", "vision_enabled": true}.

        Returns None when no backend is reachable (or the service has no
        backend at all, like the mock). Never raises — this is informational
        only and must not block the UI.
        """
        return None

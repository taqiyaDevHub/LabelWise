from fastapi import APIRouter

from backend.models.schemas import HealthResponse
from backend.services import vision_classifier

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    # vision_enabled lets the frontend (and whoever is demoing) see at a
    # glance whether the backend is on the vision path or keyword-only.
    provider = vision_classifier.provider()
    return HealthResponse(status="ok", vision_enabled=provider is not None, vision_provider=provider)

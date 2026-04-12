from fastapi import APIRouter

from app.models.schemas import HealthResponse
from app.services.ffmpeg_service import get_ffmpeg_status

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    ffmpeg_ok, ffmpeg_path = get_ffmpeg_status()
    return HealthResponse(
        ffmpeg_available=ffmpeg_ok,
        ffmpeg_path=ffmpeg_path,
    )


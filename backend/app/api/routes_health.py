from fastapi import APIRouter

from app.models.schemas import HealthResponse
from app.core.config import settings
from app.services.ffmpeg_service import get_ffmpeg_status

router = APIRouter()

def _api_key_hint(key: str) -> str:
    import hashlib

    k = (key or "").strip()
    if not k:
        return ""
    sha = hashlib.sha256(k.encode("utf-8")).hexdigest()[:10]
    tail = k[-4:] if len(k) >= 4 else k
    return f"len={len(k)} tail={tail} sha256[:10]={sha}"


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    ffmpeg_ok, ffmpeg_path = get_ffmpeg_status()
    return HealthResponse(
        ffmpeg_available=ffmpeg_ok,
        ffmpeg_path=ffmpeg_path,
        gemini_configured=bool(settings.gemini_api_key),
        gemini_agent_model=settings.gemini_agent_model or None,
        gemini_api_key_hint=_api_key_hint(settings.gemini_api_key) if settings.gemini_api_key else None,
        llm_provider=settings.llm_provider,
        ollama_base_url=settings.ollama_base_url if settings.llm_provider == "ollama" else None,
        ollama_model=settings.ollama_model if settings.llm_provider == "ollama" else None,
    )


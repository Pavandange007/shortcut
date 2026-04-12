from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # API
    api_cors_allow_origin: str = "*"

    # Storage
    uploads_root: str = "./data/uploads"
    outputs_root: str = "./data/outputs"
    # Video upload cap (mebibytes); enforced while streaming to disk.
    max_upload_mb: int = 1024

    # Full path to ffmpeg(.exe) if not on PATH (typical on Windows)
    ffmpeg_bin: str = ""

    # Models / AI keys (used later by other services)
    gemini_api_key: str = ""
    whisper_model_name: str = "medium"
    gpu_device: str = "cuda:0"

    # Auth (MVP: signed session token; swap with NextAuth/JWT later)
    auth_secret: str = "dev-change-me-dev-change-me-dev-change-me-2026"
    auth_token_ttl_seconds: int = 60 * 60 * 24 * 14


settings = Settings()


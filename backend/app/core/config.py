from pathlib import Path

from pydantic import field_validator
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
    llm_provider: str = "gemini"  # gemini | ollama
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "gemma2:2b"
    gemini_api_key: str = ""
    gemini_agent_model: str = "gemini-2.0-flash"

    @field_validator("gemini_api_key", "auth_secret", mode="before")
    @classmethod
    def _strip_whitespace(cls, v: str) -> str:
        return v.strip() if isinstance(v, str) else v

    # Vertex AI (preferred) - uses ADC credentials, not API key.
    gemini_use_vertexai: bool = False
    gcp_project: str = ""
    gcp_location: str = "us-central1"
    agent_prompt_version: str = "v1"
    refinement_max_iterations: int = 3
    refinement_quality_threshold: float = 0.78
    refinement_quality_epsilon: float = 0.02
    whisper_model_name: str = "medium"
    gpu_device: str = "cuda:0"

    # Auth (MVP: signed session token; swap with NextAuth/JWT later)
    auth_secret: str = "dev-change-me-dev-change-me-dev-change-me-2026"
    auth_token_ttl_seconds: int = 60 * 60 * 24 * 14


settings = Settings()


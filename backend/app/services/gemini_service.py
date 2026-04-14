from __future__ import annotations

import json
import threading
from typing import Final, TypeVar

from pydantic import BaseModel

import logging

from app.core.config import settings
from app.models.schemas import BestTakeResponse
from app.prompts.best_take_prompt import build_best_take_prompt

logger = logging.getLogger(__name__)

_CLIENT_LOCK: Final[threading.Lock] = threading.Lock()
_CLIENT = None

TModel = TypeVar("TModel", bound=BaseModel)


def _get_client():
    """Lazily create the google-genai client once per process."""

    global _CLIENT
    if _CLIENT is not None:
        return _CLIENT

    with _CLIENT_LOCK:
        if _CLIENT is not None:
            return _CLIENT
        try:
            from google import genai
        except ModuleNotFoundError as e:
            raise RuntimeError(
                "google-genai is not installed. Install backend requirements (e.g. pip install google-genai)."
            ) from e

        if settings.gemini_use_vertexai:
            if not settings.gcp_project.strip():
                raise RuntimeError("GCP_PROJECT is not configured (required for Vertex AI).")
            if not settings.gcp_location.strip():
                raise RuntimeError("GCP_LOCATION is not configured (required for Vertex AI).")
            _CLIENT = genai.Client(
                vertexai=True,
                project=settings.gcp_project,
                location=settings.gcp_location,
            )
            return _CLIENT

        key = settings.gemini_api_key
        if not key:
            raise RuntimeError(
                "GEMINI_API_KEY is not configured (required when GEMINI_USE_VERTEXAI=false)."
            )
        masked = f"{key[:8]}...{key[-4:]}" if len(key) > 12 else "***"
        logger.info("creating Gemini client with key=%s (len=%d)", masked, len(key))
        _CLIENT = genai.Client(api_key=key)
        return _CLIENT


def _parse_json_object_from_model_text(raw_text: str) -> str:
    text = (raw_text or "").strip()
    if not text:
        raise RuntimeError("Model returned an empty response.")
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text


def _generate_text(*, prompt: str, model_id: str) -> str:
    client = _get_client()
    try:
        response = client.models.generate_content(model=model_id, contents=prompt)
    except Exception as e:
        raise RuntimeError(f"Gemini request failed: {e}") from e
    return (getattr(response, "text", None) or "").strip()


def _generate_json_dict(*, prompt: str, model_id: str) -> dict:
    raw_text = _generate_text(prompt=prompt, model_id=model_id)
    if not raw_text:
        raise RuntimeError("Model returned an empty response.")

    json_text = _parse_json_object_from_model_text(raw_text)
    try:
        return json.loads(json_text)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Gemini output was not valid JSON: {e}. Raw: {raw_text[:300]}") from e


def generate_agent_json(
    *,
    prompt: str,
    response_model: type[TModel],
    model: str | None = None,
) -> TModel:
    """
    Call Gemini and parse a single JSON object into a Pydantic model.

    Used by multi-agent services; keeps parsing tolerant of markdown/extra text.
    """

    model_id = model or settings.gemini_agent_model
    data = _generate_json_dict(prompt=prompt, model_id=model_id)
    return response_model.model_validate(data)


def select_best_take(transcripts: list[str]) -> BestTakeResponse:
    """
    Select the best take among multiple transcript takes.

    Args:
        transcripts: List of transcript strings representing candidate takes.

    Returns:
        BestTakeResponse with the selected take index + editor-style explanation.
    """

    if len(transcripts) < 1:
        raise ValueError("transcripts must not be empty.")

    prompt = build_best_take_prompt(transcripts)
    data = _generate_json_dict(prompt=prompt, model_id="gemini-1.5-flash")
    parsed = BestTakeResponse.model_validate(data)
    if parsed.best_index < 0 or parsed.best_index >= len(transcripts):
        raise RuntimeError(
            f"Gemini best_index out of range: {parsed.best_index} for {len(transcripts)} takes."
        )

    return parsed


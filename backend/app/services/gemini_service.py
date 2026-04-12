from __future__ import annotations

import json
import threading
from typing import Final

from app.core.config import settings
from app.models.schemas import BestTakeResponse
from app.prompts.best_take_prompt import build_best_take_prompt

_CLIENT_LOCK: Final[threading.Lock] = threading.Lock()
_CLIENT = None


def _get_client():
    """
    Lazily create the google-genai client once per process.
    """

    global _CLIENT
    if _CLIENT is not None:
        return _CLIENT

    with _CLIENT_LOCK:
        if _CLIENT is not None:
            return _CLIENT
        if not settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured.")
        try:
            from google import genai
        except ModuleNotFoundError as e:
            raise RuntimeError(
                "google-genai is not installed. Install backend requirements (e.g. pip install google-genai)."
            ) from e
        _CLIENT = genai.Client(api_key=settings.gemini_api_key)
        return _CLIENT


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

    client = _get_client()
    prompt = build_best_take_prompt(transcripts)

    try:
        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=prompt,
        )
    except Exception as e:
        raise RuntimeError(f"Gemini request failed: {e}") from e

    raw_text = (getattr(response, "text", None) or "").strip()
    if not raw_text:
        raise RuntimeError("Gemini returned an empty response.")

    # Be tolerant to models returning extra whitespace; enforce strict JSON parsing.
    json_text = raw_text
    start = raw_text.find("{")
    end = raw_text.rfind("}")
    if start != -1 and end != -1 and end > start:
        json_text = raw_text[start : end + 1]

    try:
        data = json.loads(json_text)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"Gemini output was not valid JSON: {e}. Raw: {raw_text[:300]}"
        ) from e

    parsed = BestTakeResponse.model_validate(data)
    if parsed.best_index < 0 or parsed.best_index >= len(transcripts):
        raise RuntimeError(
            f"Gemini best_index out of range: {parsed.best_index} for {len(transcripts)} takes."
        )

    return parsed


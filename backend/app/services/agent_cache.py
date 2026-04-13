from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel

from app.core.config import settings

TModel = TypeVar("TModel", bound=BaseModel)


def cache_key_parts(*parts: str) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p.encode("utf-8"))
        h.update(b"\x1e")
    return h.hexdigest()


def cache_json_path(cache_dir: Path, key: str) -> Path:
    return cache_dir / f"{key}.json"


def read_cached_model(path: Path, model: type[TModel]) -> TModel | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    try:
        return model.model_validate(data)
    except Exception:
        return None


def write_cached_payload(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def build_agent_inputs_hash(
    *,
    agent_name: str,
    transcript_fingerprint: str,
    suffix: str = "",
) -> str:
    parts = [settings.agent_prompt_version, agent_name, transcript_fingerprint]
    if suffix:
        parts.append(suffix)
    return cache_key_parts(*parts)

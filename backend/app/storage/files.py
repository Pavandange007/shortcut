from __future__ import annotations

from pathlib import Path
from typing import Final

from app.core.config import settings


UPLOADS_ROOT: Final[Path] = Path(settings.uploads_root).resolve()
OUTPUTS_ROOT: Final[Path] = Path(settings.outputs_root).resolve()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def get_user_root(user_id: str) -> Path:
    root = UPLOADS_ROOT / user_id
    ensure_dir(root)
    return root


def get_job_root(user_id: str, job_id: str) -> Path:
    root = get_user_root(user_id) / job_id
    ensure_dir(root)
    ensure_dir(root / "outputs")
    return root


def get_video_path(user_id: str, job_id: str) -> Path:
    """
    Return the uploaded video path.

    MVP detail:
    The upload endpoint preserves the original file extension (e.g. input_video.mp4),
    but other services expect a stable getter. If `input_video` doesn't exist,
    we fall back to `input_video.*` (most recently modified).
    """

    root = get_job_root(user_id, job_id)
    base = root / "input_video"
    if base.exists():
        return base

    matches = sorted(
        root.glob("input_video.*"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if matches:
        return matches[0]
    return base


def get_transcript_json_path(user_id: str, job_id: str) -> Path:
    return get_job_root(user_id, job_id) / "transcript.json"


def get_timeline_json_path(user_id: str, job_id: str) -> Path:
    return get_job_root(user_id, job_id) / "timeline.json"


def get_outputs_root(user_id: str, job_id: str) -> Path:
    return get_job_root(user_id, job_id) / "outputs"


def get_rough_cut_path(user_id: str, job_id: str) -> Path:
    return get_outputs_root(user_id, job_id) / "rough_cut.mp4"


def get_captions_json_path(user_id: str, job_id: str) -> Path:
    return get_job_root(user_id, job_id) / "captions.json"


def get_burned_captions_path(user_id: str, job_id: str) -> Path:
    return get_outputs_root(user_id, job_id) / "captions_burned.mp4"


def get_agents_dir(user_id: str, job_id: str) -> Path:
    d = get_job_root(user_id, job_id) / "agents"
    ensure_dir(d)
    return d


def get_agent_cache_dir(user_id: str, job_id: str) -> Path:
    d = get_agents_dir(user_id, job_id) / "cache"
    ensure_dir(d)
    return d


def get_content_analysis_json_path(user_id: str, job_id: str) -> Path:
    return get_agents_dir(user_id, job_id) / "content_analysis.json"


def get_agent_messages_jsonl_path(user_id: str, job_id: str) -> Path:
    return get_agents_dir(user_id, job_id) / "messages.jsonl"


def get_agents_iterations_dir(user_id: str, job_id: str) -> Path:
    d = get_agents_dir(user_id, job_id) / "iterations"
    ensure_dir(d)
    return d


def get_story_analysis_json_path(user_id: str, job_id: str) -> Path:
    return get_agents_dir(user_id, job_id) / "story_analysis.json"


def get_viral_analysis_json_path(user_id: str, job_id: str) -> Path:
    return get_agents_dir(user_id, job_id) / "viral_analysis.json"


def get_title_hook_analysis_json_path(user_id: str, job_id: str) -> Path:
    return get_agents_dir(user_id, job_id) / "title_hook_analysis.json"


def get_refinement_summary_json_path(user_id: str, job_id: str) -> Path:
    return get_agents_dir(user_id, job_id) / "refinement.json"


def get_refinement_iteration_json_path(user_id: str, job_id: str, iteration_index: int) -> Path:
    return get_agents_iterations_dir(user_id, job_id) / f"{iteration_index:02d}.json"


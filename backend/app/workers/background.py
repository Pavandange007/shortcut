from __future__ import annotations

import json
import logging
import threading
import time
from pathlib import Path
from typing import Final

logger = logging.getLogger(__name__)

from app.models.schemas import BestTakeResponse
from app.services.caption_service import group_words_into_captions
from app.services.ffmpeg_service import export_rough_cut
from app.services.rough_cut_captions_service import burn_captions_onto_existing_rough_cut
from app.services.gemini_service import select_best_take
from app.services.silence_service import build_speech_timeline, compute_silence_segments
from app.services.whisper_service import transcribe_with_word_timestamps
from app.services.agent_orchestrator import run_post_transcript_agents
from app.services.jobs_service import job_store
from app.storage.files import (
    get_captions_json_path,
    get_timeline_json_path,
    get_transcript_json_path,
    get_video_path,
    get_rough_cut_path,
)

_WORKER_LOCK: Final[threading.Lock] = threading.Lock()


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def _get_best_take_index(transcript_text: str) -> BestTakeResponse | None:
    # For MVP, we treat the single transcript as "take 0".
    # If Gemini isn't configured, we skip (best_index=0).
    try:
        return select_best_take([transcript_text])
    except Exception:
        return BestTakeResponse(best_index=0, explanation="Gemini unavailable; defaulting to take 0.")


def run_job_pipeline(*, user_id: str, job_id: str) -> None:
    """
    Run the 4-layer pipeline sequentially after upload.

    This is an MVP background worker (in-process). Swap this with Celery/RQ
    for production.
    """

    record = job_store.get_job(job_id=job_id, user_id=user_id)
    if record is None:
        logger.error("pipeline skipped: no job record user_id=%s job_id=%s", user_id, job_id)
        return

    # Only one run per job from "queued" (avoids parallel double-starts).
    with _WORKER_LOCK:
        if record.overall_status != "queued":
            logger.info(
                "pipeline skipped: job not queued (status=%s) user_id=%s job_id=%s",
                record.overall_status,
                user_id,
                job_id,
            )
            return
        record.overall_status = "running"
        job_store.save_job(record)

    logger.info("pipeline start user_id=%s job_id=%s", user_id, job_id)

    video_path = get_video_path(user_id=user_id, job_id=job_id)
    if not video_path.exists():
        record.overall_status = "failed"
        record.steps["silence_removal"] = "failed"
        record.outputs["error"] = "input_video missing"
        job_store.save_job(record)
        logger.error(
            "pipeline failed: input video missing user_id=%s job_id=%s expected=%s",
            user_id,
            job_id,
            video_path,
        )
        return

    record.steps["silence_removal"] = "running"
    job_store.save_job(record)
    try:
        transcript = transcribe_with_word_timestamps(video_path)
        transcript_path = get_transcript_json_path(user_id=user_id, job_id=job_id)
        _write_json(
            transcript_path,
            {"words": [w.model_dump(mode="json") for w in transcript.words], "raw_text": transcript.raw_text},
        )

        silences = compute_silence_segments(transcript.words)
        timeline = build_speech_timeline(transcript.words, silences)
        timeline_path = get_timeline_json_path(user_id=user_id, job_id=job_id)
        _write_json(timeline_path, [seg.model_dump(mode="json") for seg in timeline])

        record.steps["silence_removal"] = "done"
        job_store.save_job(record)
        logger.info(
            "pipeline transcript+timeline ok user_id=%s job_id=%s words=%d",
            user_id,
            job_id,
            len(transcript.words),
        )

        try:
            run_post_transcript_agents(
                user_id=user_id,
                job_id=job_id,
                transcript=transcript,
                record=record,
            )
        except Exception as agent_exc:
            logger.exception(
                "post-transcript agent phase failed user_id=%s job_id=%s",
                user_id,
                job_id,
            )
            record.outputs["agentPhaseError"] = str(agent_exc)
            job_store.save_job(record)
    except Exception as e:
        record.steps["silence_removal"] = "failed"
        record.overall_status = "failed"
        record.outputs["error"] = f"transcription/timeline failed: {e}"
        job_store.save_job(record)
        logger.exception(
            "pipeline failed at transcript/timeline user_id=%s job_id=%s",
            user_id,
            job_id,
        )
        return

    record.steps["best_take"] = "running"
    job_store.save_job(record)
    try:
        best_take = _get_best_take_index(transcript_text=transcript.raw_text)
        record.outputs["bestTakeIndex"] = best_take.best_index
        record.outputs["bestTakeExplanation"] = best_take.explanation
        record.steps["best_take"] = "done"
        job_store.save_job(record)
    except Exception as e:
        record.steps["best_take"] = "failed"
        record.outputs["error"] = f"best-take failed: {e}"
        job_store.save_job(record)

    # Captions JSON (source timeline). Burn-in runs on rough_cut.mp4 after export.
    record.steps["captions"] = "running"
    job_store.save_job(record)
    try:
        captions = group_words_into_captions(transcript.words)
        captions_path = get_captions_json_path(user_id=user_id, job_id=job_id)
        _write_json(
            captions_path,
            [c.model_dump(mode="json") for c in captions],
        )
        record.outputs["burnedCaptionsPath"] = None

        record.steps["captions"] = "done"
        job_store.save_job(record)
        logger.info("pipeline captions ok user_id=%s job_id=%s", user_id, job_id)
    except Exception as e:
        record.steps["captions"] = "failed"
        record.outputs["error"] = f"captions failed: {e}"
        record.overall_status = "failed"
        job_store.save_job(record)
        logger.exception("pipeline failed at captions user_id=%s job_id=%s", user_id, job_id)
        return

    # Rough cut export depends on FFmpeg binary.
    record.steps["export"] = "running"
    job_store.save_job(record)
    try:
        # Read timeline back from disk to keep the interfaces decoupled.
        timeline_path = get_timeline_json_path(user_id=user_id, job_id=job_id)
        raw_timeline = json.loads(timeline_path.read_text(encoding="utf-8-sig"))
        timeline = raw_timeline  # list of dicts
        keep_segments = [
            (int(item["start_ms"]), int(item["end_ms"]))
            for item in timeline
            if item.get("keep_audio")
        ]
        if not keep_segments:
            raise ValueError("No keep segments found in timeline.json")

        output_path = get_rough_cut_path(user_id=user_id, job_id=job_id)
        record.outputs.pop("error_caption_burn", None)
        export_rough_cut(video_path, keep_segments, output_path, crossfade_ms=150)
        try:
            burn_captions_onto_existing_rough_cut(
                rough_cut_path=output_path,
                transcript_words=transcript.words,
                keep_segments=keep_segments,
            )
        except Exception as burn_exc:
            record.outputs["error_caption_burn"] = str(burn_exc)
            job_store.save_job(record)
            logger.exception(
                "pipeline caption burn onto rough cut failed user_id=%s job_id=%s",
                user_id,
                job_id,
            )
        # Expose URL only after burn attempt so clients never cache a pre-burn file.
        record.outputs["roughCutUrl"] = f"/jobs/{job_id}/rough-cut"
        record.outputs["media_revision"] = int(time.time() * 1000)
        record.steps["export"] = "done"
        record.overall_status = "completed"
        job_store.save_job(record)
        logger.info("pipeline completed user_id=%s job_id=%s", user_id, job_id)
    except Exception as e:
        record.steps["export"] = "failed"
        record.outputs["error_export"] = str(e)
        # Captions + transcript are still usable even if FFmpeg export isn't available.
        record.overall_status = "completed"
        job_store.save_job(record)
        logger.error(
            "pipeline export failed user_id=%s job_id=%s — stored in outputs.error_export: %s",
            user_id,
            job_id,
            e,
        )


from __future__ import annotations

import json
import subprocess
import time
from fastapi import APIRouter, Header, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse

from app.models.schemas import (
    CaptionsRequest,
    CaptionsResponse,
    ExportRequest,
    ExportResponse,
    SilenceTimelineResponse,
    TranscriptResponse,
    TimelineSegment,
)
from app.services.jobs_service import job_store
from app.services.auth_service import try_get_user_id_from_authorization
from app.services.caption_service import group_words_into_captions
from app.services.ffmpeg_service import burn_in_captions
from app.services.rough_cut_captions_service import (
    burn_captions_onto_existing_rough_cut,
    export_rough_cut_and_burn_captions,
)
from app.services.silence_service import build_speech_timeline, compute_silence_segments
from app.storage.files import (
    get_burned_captions_path,
    get_captions_json_path,
    get_rough_cut_path,
    get_timeline_json_path,
    get_transcript_json_path,
    get_video_path,
)

router = APIRouter()


def resolve_user_id(authorization: str | None, x_user_id: str | None) -> str:
    user_id = try_get_user_id_from_authorization(authorization)
    return user_id or x_user_id or "anonymous"


@router.post("/jobs/{job_id}/silence-timeline", response_model=SilenceTimelineResponse)
async def silence_timeline_job(
    job_id: str,
    authorization: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None),
) -> SilenceTimelineResponse:
    """
    Use Whisper word timestamps to produce a cut timeline by removing
    silences larger than 1s (with heuristics to preserve natural pauses).
    """

    user_id = resolve_user_id(authorization, x_user_id)
    record = job_store.get_job(job_id=job_id, user_id=user_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Job not found.")

    transcript_path = get_transcript_json_path(user_id=user_id, job_id=job_id)
    if not transcript_path.exists():
        raise HTTPException(
            status_code=400,
            detail="transcript.json not found. Call /jobs/{job_id}/transcript first.",
        )

    # PowerShell `Set-Content -Encoding UTF8` may write a UTF-8 BOM.
    raw = json.loads(transcript_path.read_text(encoding="utf-8-sig"))
    transcript = TranscriptResponse.model_validate(raw)

    silences = compute_silence_segments(transcript.words)
    timeline = build_speech_timeline(transcript.words, silences)

    timeline_path = get_timeline_json_path(user_id=user_id, job_id=job_id)
    timeline_path.write_text(
        json.dumps([seg.model_dump(mode="json") for seg in timeline], ensure_ascii=False),
        encoding="utf-8",
    )

    record.steps["silence_removal"] = "done"
    record.overall_status = "running"
    job_store.save_job(record)

    return SilenceTimelineResponse(timeline=timeline)


@router.post("/jobs/{job_id}/captions", response_model=CaptionsResponse)
async def captions_job(
    job_id: str,
    request: CaptionsRequest,
    authorization: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None),
) -> CaptionsResponse:
    """
    Group Whisper word timestamps into readable caption lines, optionally
    burn-in captions to the video via FFmpeg.
    """

    user_id = resolve_user_id(authorization, x_user_id)
    record = job_store.get_job(job_id=job_id, user_id=user_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Job not found.")

    transcript_path = get_transcript_json_path(user_id=user_id, job_id=job_id)
    if not transcript_path.exists():
        raise HTTPException(
            status_code=400,
            detail="transcript.json not found. Call /jobs/{job_id}/transcript first.",
        )

    raw = json.loads(transcript_path.read_text(encoding="utf-8-sig"))
    transcript = TranscriptResponse.model_validate(raw)

    captions = group_words_into_captions(
        transcript.words,
        max_chars=request.max_chars,
        max_duration_ms=request.max_duration_ms,
    )

    captions_path = get_captions_json_path(user_id=user_id, job_id=job_id)
    captions_path.write_text(
        json.dumps([c.model_dump(mode="json") for c in captions], ensure_ascii=False),
        encoding="utf-8",
    )

    record.steps["captions"] = "done"
    record.overall_status = "running"
    job_store.save_job(record)

    if not request.burn_in:
        return CaptionsResponse(captions=captions, burned_captions_url=None)

    rough_path = get_rough_cut_path(user_id=user_id, job_id=job_id)
    timeline_path = get_timeline_json_path(user_id=user_id, job_id=job_id)
    if rough_path.exists() and timeline_path.exists():
        raw_tl = json.loads(timeline_path.read_text(encoding="utf-8-sig"))
        keep_segments: list[tuple[int, int]] = [
            (int(item["start_ms"]), int(item["end_ms"]))
            for item in raw_tl
            if item.get("keep_audio")
        ]
        if keep_segments:
            try:
                burn_captions_onto_existing_rough_cut(
                    rough_cut_path=rough_path,
                    transcript_words=transcript.words,
                    keep_segments=keep_segments,
                )
            except FileNotFoundError as e:
                raise HTTPException(status_code=500, detail=str(e)) from e
            except RuntimeError as e:
                raise HTTPException(status_code=500, detail=str(e)) from e
            return CaptionsResponse(
                captions=captions,
                burned_captions_url=f"/jobs/{job_id}/rough-cut",
            )

    video_path = get_video_path(user_id=user_id, job_id=job_id)
    if not video_path.exists():
        raise HTTPException(
            status_code=400,
            detail="No uploaded video found for this job. Upload a video first.",
        )

    burned_path = get_burned_captions_path(user_id=user_id, job_id=job_id)
    try:
        burn_in_captions(
            video_path,
            captions,
            burned_path,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    except subprocess.CalledProcessError as e:
        raise HTTPException(
            status_code=500,
            detail=f"ffmpeg failed: {e}",
        ) from e

    burned_url = burned_path.as_posix()
    return CaptionsResponse(captions=captions, burned_captions_url=burned_url)


@router.post("/jobs/{job_id}/export", response_model=ExportResponse)
async def export_job(
    job_id: str,
    request: ExportRequest,
    authorization: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None),
) -> ExportResponse:
    """
    Export a rough cut MP4 by trimming + stitching keep segments from timeline.json.
    """

    user_id = resolve_user_id(authorization, x_user_id)
    record = job_store.get_job(job_id=job_id, user_id=user_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Job not found.")

    timeline_path = get_timeline_json_path(user_id=user_id, job_id=job_id)
    if not timeline_path.exists():
        raise HTTPException(
            status_code=400,
            detail="timeline.json not found. Call /jobs/{job_id}/silence-timeline first.",
        )

    raw = json.loads(timeline_path.read_text(encoding="utf-8-sig"))
    timeline = [TimelineSegment.model_validate(item) for item in raw]

    keep_segments: list[tuple[int, int]] = [
        (seg.start_ms, seg.end_ms) for seg in timeline if seg.keep_audio
    ]
    if not keep_segments:
        raise HTTPException(status_code=400, detail="No keep segments found in timeline.json.")

    video_path = get_video_path(user_id=user_id, job_id=job_id)
    if not video_path.exists():
        raise HTTPException(
            status_code=400,
            detail="No uploaded video found for this job. Upload a video first.",
        )

    output_path = get_rough_cut_path(user_id=user_id, job_id=job_id)

    transcript_path = get_transcript_json_path(user_id=user_id, job_id=job_id)
    if not transcript_path.exists():
        raise HTTPException(
            status_code=400,
            detail="transcript.json not found. Run transcription for this job first.",
        )
    raw_tr = json.loads(transcript_path.read_text(encoding="utf-8-sig"))
    tr_model = TranscriptResponse.model_validate(raw_tr)

    record.steps["export"] = "running"
    record.overall_status = "running"
    job_store.save_job(record)

    try:
        await run_in_threadpool(
            export_rough_cut_and_burn_captions,
            video_path,
            keep_segments,
            output_path,
            tr_model.words,
            crossfade_ms=request.crossfade_ms,
        )
    except FileNotFoundError as e:
        record.steps["export"] = "failed"
        raise HTTPException(status_code=500, detail=str(e)) from e
    except RuntimeError as e:
        record.steps["export"] = "failed"
        raise HTTPException(status_code=500, detail=str(e)) from e

    record.steps["export"] = "done"
    record.outputs["roughCutUrl"] = f"/jobs/{job_id}/rough-cut"
    record.outputs["media_revision"] = int(time.time() * 1000)
    record.overall_status = "completed"
    job_store.save_job(record)

    return ExportResponse(rough_cut_url=record.outputs["roughCutUrl"])


@router.get("/jobs/{job_id}/rough-cut")
async def rough_cut_file(
    job_id: str,
    authorization: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None),
) -> FileResponse:
    """
    Serve the exported rough-cut MP4.
    """

    user_id = resolve_user_id(authorization, x_user_id)
    record = job_store.get_job(job_id=job_id, user_id=user_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Job not found.")

    path = get_rough_cut_path(user_id=user_id, job_id=job_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Rough cut not exported yet.")

    return FileResponse(path, media_type="video/mp4")


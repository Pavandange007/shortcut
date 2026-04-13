from __future__ import annotations

import json
from fastapi import APIRouter, Header, HTTPException
from fastapi.concurrency import run_in_threadpool

from app.models.schemas import TranscriptResponse
from app.services.auth_service import try_get_user_id_from_authorization
from app.services.jobs_service import job_store
from app.services.whisper_service import transcribe_with_word_timestamps
from app.storage.files import get_transcript_json_path, get_video_path

router = APIRouter()


def resolve_user_id(authorization: str | None, x_user_id: str | None) -> str:
    user_id = try_get_user_id_from_authorization(authorization)
    return user_id or x_user_id or "anonymous"


@router.post("/jobs/{job_id}/transcript", response_model=TranscriptResponse)
async def transcript_job(
    job_id: str,
    authorization: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None),
) -> TranscriptResponse:
    """
    Generate a word-timestamp transcript JSON for the uploaded video.

    The result is persisted to `transcript.json` under the job folder.
    """

    user_id = resolve_user_id(authorization, x_user_id)
    record = job_store.get_job(job_id=job_id, user_id=user_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Job not found.")

    record.overall_status = "running"
    record.steps["silence_removal"] = "running"
    job_store.save_job(record)

    video_path = get_video_path(user_id=user_id, job_id=job_id)
    if not video_path.exists():
        raise HTTPException(
            status_code=400,
            detail="No uploaded video found for this job. Upload a video first.",
        )

    transcript = await run_in_threadpool(transcribe_with_word_timestamps, video_path)

    transcript_path = get_transcript_json_path(user_id=user_id, job_id=job_id)
    transcript_path.write_text(
        json.dumps(transcript.model_dump(mode="json"), ensure_ascii=False)
    )

    record.steps["silence_removal"] = "done"
    record.overall_status = "running"
    job_store.save_job(record)

    return transcript


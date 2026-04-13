from __future__ import annotations

from pathlib import Path
import threading

from fastapi import APIRouter, File, Header, HTTPException, UploadFile, status

from app.core.config import settings
from app.models.schemas import JobCreateResponse, JobResponse, JobUploadResponse
from app.services.auth_service import try_get_user_id_from_authorization
from app.services.jobs_service import job_store
from app.storage.files import get_video_path

router = APIRouter()


def _run_pipeline_thread(*, user_id: str, job_id: str) -> None:
    """Import worker only when needed so API startup does not load Whisper/Gemini stack."""

    from app.workers.background import run_job_pipeline

    run_job_pipeline(user_id=user_id, job_id=job_id)


def resolve_user_id(authorization: str | None, x_user_id: str | None) -> str:
    user_id = try_get_user_id_from_authorization(authorization)
    return user_id or x_user_id or "anonymous"


@router.post("/jobs", response_model=JobCreateResponse)
def create_job(
    authorization: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None),
) -> JobCreateResponse:
    user_id = resolve_user_id(authorization, x_user_id)
    record = job_store.create_job(user_id=user_id)
    return JobCreateResponse(job_id=record.job_id)


@router.post("/jobs/{job_id}/upload", response_model=JobUploadResponse)
async def upload_job_video(
    job_id: str,
    file: UploadFile = File(...),
    authorization: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None),
) -> JobUploadResponse:
    user_id = resolve_user_id(authorization, x_user_id)
    record = job_store.get_job(job_id=job_id, user_id=user_id)
    if record is None:
        owner = job_store.find_job_owner(job_id=job_id)
        if owner and owner != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Job belongs to a different session.",
            )
        raise HTTPException(status_code=404, detail="Job not found.")

    video_path = get_video_path(user_id=user_id, job_id=job_id)
    suffix = Path(file.filename).suffix
    if suffix:
        video_path = video_path.with_suffix(suffix)
        video_path.parent.mkdir(parents=True, exist_ok=True)

    max_bytes = settings.max_upload_mb * 1024 * 1024
    written = 0
    try:
        with video_path.open("wb") as out_file:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                written += len(chunk)
                if written > max_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File exceeds max size of {settings.max_upload_mb} MB.",
                    )
                out_file.write(chunk)
    except HTTPException:
        video_path.unlink(missing_ok=True)
        raise
    finally:
        await file.close()

    # Kick off the MVP pipeline in a dedicated thread to avoid blocking.
    threading.Thread(
        target=_run_pipeline_thread,
        kwargs={"user_id": user_id, "job_id": job_id},
        daemon=True,
    ).start()

    return JobUploadResponse(job_id=job_id, status=record.overall_status)


@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(
    job_id: str,
    authorization: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None),
) -> JobResponse:
    user_id = resolve_user_id(authorization, x_user_id)
    record = job_store.get_job(job_id=job_id, user_id=user_id)
    if record is None:
        owner = job_store.find_job_owner(job_id=job_id)
        if owner and owner != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Job belongs to a different session.",
            )
        raise HTTPException(status_code=404, detail="Job not found.")
    return job_store.to_response(record)


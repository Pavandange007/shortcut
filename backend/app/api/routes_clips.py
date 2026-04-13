from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Query, status
from fastapi.responses import FileResponse

from app.api.routes_uploads import resolve_user_id
from app.services.jobs_service import job_store
from app.services.ffmpeg_service import export_clip, ffmpeg_available
from app.storage.files import get_clip_path, get_video_path

router = APIRouter()

_MAX_CLIP_MS = 5 * 60 * 1000  # 5 minutes for preview


@router.get("/jobs/{job_id}/clip")
def get_job_clip(
    job_id: str,
    start_ms: int = Query(..., alias="startMs", ge=0),
    end_ms: int = Query(..., alias="endMs", ge=0),
    authorization: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None),
) -> FileResponse:
    """
    Export and serve a preview clip for a Gemini-proposed time range.

    Clips are cached on disk under the job outputs folder.
    """

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

    if end_ms <= start_ms:
        raise HTTPException(status_code=400, detail="endMs must be greater than startMs.")
    if (end_ms - start_ms) > _MAX_CLIP_MS:
        raise HTTPException(
            status_code=400,
            detail=f"Clip too long; max is {_MAX_CLIP_MS} ms.",
        )
    if not ffmpeg_available():
        raise HTTPException(status_code=500, detail="FFmpeg is required to export preview clips.")

    src = get_video_path(user_id=user_id, job_id=job_id)
    if not src.exists():
        raise HTTPException(status_code=400, detail="No uploaded video found for this job.")

    out_path = get_clip_path(user_id=user_id, job_id=job_id, start_ms=start_ms, end_ms=end_ms)
    if not out_path.exists():
        try:
            export_clip(video_path=src, start_ms=start_ms, end_ms=end_ms, output_path=out_path)
        except FileNotFoundError as e:
            raise HTTPException(status_code=500, detail=str(e)) from e
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        except RuntimeError as e:
            raise HTTPException(status_code=500, detail=str(e)) from e

    return FileResponse(out_path, media_type="video/mp4")


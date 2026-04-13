from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException

from app.api.routes_uploads import resolve_user_id
from app.models.schemas import JobFeedbackRequest, JobFeedbackResponse
from app.services.jobs_service import job_store

router = APIRouter()


@router.post("/jobs/{job_id}/feedback", response_model=JobFeedbackResponse)
def post_job_feedback(
    job_id: str,
    body: JobFeedbackRequest,
    authorization: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None),
) -> JobFeedbackResponse:
    """
    Store user notes and constraints for future refinement runs.
    Does not automatically re-run the pipeline (MVP).
    """

    user_id = resolve_user_id(authorization, x_user_id)
    record = job_store.get_job(job_id=job_id, user_id=user_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Job not found.")

    record.outputs["userFeedback"] = body.model_dump(mode="json", by_alias=True)
    return JobFeedbackResponse(job_id=job_id, ok=True)

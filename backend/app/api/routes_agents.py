from __future__ import annotations

import json
import re
import threading
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException

from app.api.routes_uploads import resolve_user_id
from app.models.schemas import (
    JobChatMessage,
    JobChatRequest,
    JobChatResponse,
    JobFeedbackRequest,
    JobFeedbackResponse,
    TranscriptResponse,
)
from app.services.agent_orchestrator import AgentOrchestrator
from app.services.jobs_service import job_store
from app.storage.files import get_transcript_json_path

router = APIRouter()


def _parse_chat_clip_constraints(message: str) -> tuple[int, int]:
    """
    Best-effort parsing for clip constraints from a natural language request.

    Returns:
        (target_duration_s, clip_count)
    """

    m = message.lower()
    dur = 30
    dur_match = re.search(r"\b(\d{1,3})\s*(seconds|second|sec|s)\b", m)
    if dur_match:
        try:
            dur = int(dur_match.group(1))
        except ValueError:
            dur = 30

    count = 6
    count_match = re.search(r"\b(\d{1,2})\s*(clips|clip)\b", m)
    if count_match:
        try:
            count = int(count_match.group(1))
        except ValueError:
            count = 6

    dur = max(5, min(dur, 120))
    count = max(1, min(count, 12))
    return dur, count


def _append_chat_message(record, msg: JobChatMessage) -> None:
    hist = record.outputs.setdefault("chatHistory", [])
    if not isinstance(hist, list):
        hist = []
        record.outputs["chatHistory"] = hist
    hist.append(msg.model_dump(mode="json", by_alias=True))


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
    job_store.save_job(record)
    return JobFeedbackResponse(job_id=job_id, ok=True)


@router.post("/jobs/{job_id}/chat", response_model=JobChatResponse)
def post_job_chat(
    job_id: str,
    body: JobChatRequest,
    authorization: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None),
) -> JobChatResponse:
    user_id = resolve_user_id(authorization, x_user_id)
    record = job_store.get_job(job_id=job_id, user_id=user_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Job not found.")

    now = datetime.now(timezone.utc).isoformat()
    user_msg_id = uuid.uuid4().hex
    assistant_msg_id = uuid.uuid4().hex

    _append_chat_message(
        record,
        JobChatMessage(
            id=user_msg_id,
            role="user",
            text=body.message,
            created_at=now,
            status="done",
        ),
    )
    _append_chat_message(
        record,
        JobChatMessage(
            id=assistant_msg_id,
            role="assistant",
            text="Working…",
            created_at=now,
            status="queued",
        ),
    )
    job_store.save_job(record)

    target_duration_s, clip_count = _parse_chat_clip_constraints(body.message)

    def _run_chat() -> None:
        r = job_store.get_job(job_id=job_id, user_id=user_id)
        if r is None:
            return

        # Mark assistant message running.
        hist = r.outputs.get("chatHistory")
        if isinstance(hist, list):
            for item in hist:
                if isinstance(item, dict) and item.get("id") == assistant_msg_id:
                    item["status"] = "running"
                    item["text"] = "Running agents…"
                    break
            job_store.save_job(r)

        try:
            transcript_path = get_transcript_json_path(user_id=user_id, job_id=job_id)
            if not transcript_path.exists():
                raise RuntimeError(
                    "Transcript not found yet. Upload/run the pipeline first, then try again."
                )
            raw = json.loads(transcript_path.read_text(encoding="utf-8-sig"))
            transcript = TranscriptResponse.model_validate(raw)

            AgentOrchestrator().run_chat_clips_request(
                user_id=user_id,
                job_id=job_id,
                transcript=transcript,
                record=r,
                user_request=body.message,
                target_duration_s=target_duration_s,
                clip_count=clip_count,
            )

            hist2 = r.outputs.get("chatHistory")
            if isinstance(hist2, list):
                for item in hist2:
                    if isinstance(item, dict) and item.get("id") == assistant_msg_id:
                        item["status"] = "done"
                        item["text"] = (
                            f"Generated viral clip candidates (target ~{target_duration_s}s). "
                            "See “Viral clips & titles” below."
                        )
                        break
            job_store.save_job(r)
        except Exception as e:
            hist3 = r.outputs.get("chatHistory")
            if isinstance(hist3, list):
                for item in hist3:
                    if isinstance(item, dict) and item.get("id") == assistant_msg_id:
                        item["status"] = "error"
                        item["text"] = "Chat request failed."
                        item["error"] = str(e)
                        break
            job_store.save_job(r)

    threading.Thread(target=_run_chat, daemon=True).start()

    return JobChatResponse(
        job_id=job_id,
        accepted=True,
        user_message_id=user_msg_id,
        assistant_message_id=assistant_msg_id,
    )

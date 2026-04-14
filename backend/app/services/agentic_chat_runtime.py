from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

from app.models.schemas import TranscriptResponse
from app.services.agent_orchestrator import AgentOrchestrator
from app.services.jobs_service import JobRecord, job_store
from app.storage.files import get_transcript_json_path

AgenticEventType = Literal[
    "plan",
    "step_start",
    "step_done",
    "tool_call",
    "tool_result",
    "warning",
    "error",
]


@dataclass(frozen=True)
class AgenticEvent:
    ts: str
    type: AgenticEventType
    message: str
    data: dict[str, Any] | None = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append_event(record: JobRecord, event: AgenticEvent) -> None:
    events = record.outputs.setdefault("agenticChatEvents", [])
    if not isinstance(events, list):
        events = []
        record.outputs["agenticChatEvents"] = events
    payload: dict[str, Any] = {
        "ts": event.ts,
        "type": event.type,
        "message": event.message,
    }
    if event.data:
        payload["data"] = event.data
    events.append(payload)


def _update_assistant_message(
    *,
    record: JobRecord,
    assistant_msg_id: str,
    status: str,
    text: str,
    error: str | None = None,
) -> None:
    hist = record.outputs.get("chatHistory")
    if not isinstance(hist, list):
        return
    for item in hist:
        if isinstance(item, dict) and item.get("id") == assistant_msg_id:
            item["status"] = status
            item["text"] = text
            if error is not None:
                item["error"] = error
            break


def run_agentic_chat_clips(
    *,
    user_id: str,
    job_id: str,
    assistant_msg_id: str,
    user_request: str,
    target_duration_s: int,
    clip_count: int,
) -> None:
    """
    Cursor-like agent loop wrapper around the existing chat clip orchestrator.

    Writes incremental progress to:
    - job.outputs["agenticChatEvents"]: list of events for UI
    - job.outputs["chatHistory"][assistant]: status/text updates
    """

    record = job_store.get_job(job_id=job_id, user_id=user_id)
    if record is None:
        return

    _append_event(
        record,
        AgenticEvent(
            ts=_now(),
            type="plan",
            message="Plan: read transcript → analyze content/story → propose clips → generate titles/hooks → finalize.",
            data={"targetDurationS": target_duration_s, "clipCount": clip_count},
        ),
    )
    _update_assistant_message(
        record=record,
        assistant_msg_id=assistant_msg_id,
        status="running",
        text="Plan created. Starting…",
    )
    job_store.save_job(record)

    transcript_path = get_transcript_json_path(user_id=user_id, job_id=job_id)
    if not transcript_path.exists():
        err = "Transcript not found yet. Upload/run the pipeline first, then try again."
        _append_event(record, AgenticEvent(ts=_now(), type="error", message=err))
        _update_assistant_message(
            record=record,
            assistant_msg_id=assistant_msg_id,
            status="error",
            text="Chat request failed.",
            error=err,
        )
        job_store.save_job(record)
        return

    try:
        _append_event(record, AgenticEvent(ts=_now(), type="step_start", message="Loading transcript artifact"))
        raw = json.loads(transcript_path.read_text(encoding="utf-8-sig"))
        transcript = TranscriptResponse.model_validate(raw)
        _append_event(
            record,
            AgenticEvent(
                ts=_now(),
                type="step_done",
                message="Transcript loaded",
                data={"wordCount": len(transcript.words)},
            ),
        )
        _update_assistant_message(
            record=record,
            assistant_msg_id=assistant_msg_id,
            status="running",
            text="Transcript loaded. Running agents…",
        )
        job_store.save_job(record)

        _append_event(record, AgenticEvent(ts=_now(), type="tool_call", message="AgentOrchestrator.run_chat_clips_request"))
        job_store.save_job(record)

        AgentOrchestrator().run_chat_clips_request(
            user_id=user_id,
            job_id=job_id,
            transcript=transcript,
            record=record,
            user_request=user_request,
            target_duration_s=target_duration_s,
            clip_count=clip_count,
        )

        clip_count_out = len((record.outputs.get("viralAnalysis") or {}).get("clips", [])) if isinstance(record.outputs.get("viralAnalysis"), dict) else None
        used_heuristic = bool(record.outputs.get("chatClipsUsedHeuristic"))
        clip_err = record.outputs.get("chatClipsError")

        _append_event(
            record,
            AgenticEvent(
                ts=_now(),
                type="tool_result",
                message="Clip candidates generated",
                data={"clipCount": clip_count_out, "usedHeuristic": used_heuristic},
            ),
        )
        if used_heuristic and clip_err:
            _append_event(record, AgenticEvent(ts=_now(), type="warning", message=f"Gemini failed; fallback used. {clip_err}"))

        summary = f"Generated viral clip candidates (target ~{target_duration_s}s)."
        if used_heuristic:
            summary += " Gemini was unavailable, so I used a heuristic fallback."
        summary += " See “Viral clips & titles” below."

        _update_assistant_message(
            record=record,
            assistant_msg_id=assistant_msg_id,
            status="done",
            text=summary,
            error=clip_err if used_heuristic and isinstance(clip_err, str) else None,
        )
        job_store.save_job(record)
    except Exception as e:
        msg = str(e)
        _append_event(record, AgenticEvent(ts=_now(), type="error", message=msg))
        _update_assistant_message(
            record=record,
            assistant_msg_id=assistant_msg_id,
            status="error",
            text="Chat request failed.",
            error=msg,
        )
        job_store.save_job(record)


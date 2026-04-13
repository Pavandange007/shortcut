from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.models.schemas import (
    JobResponse,
    JobStepKey,
    OverallStatus,
    StepState,
)
from app.storage.files import UPLOADS_ROOT, ensure_dir, get_job_root


@dataclass
class JobRecord:
    job_id: str
    user_id: str
    created_at: datetime
    overall_status: OverallStatus
    steps: dict[JobStepKey, StepState] = field(default_factory=dict)
    outputs: dict[str, Any] = field(default_factory=dict)

    def to_persisted(self) -> "PersistedJobRecord":
        return PersistedJobRecord(
            job_id=self.job_id,
            user_id=self.user_id,
            created_at=self.created_at,
            overall_status=self.overall_status,
            steps=self.steps,
            outputs=self.outputs,
        )


class PersistedJobRecord(BaseModel):
    job_id: str
    user_id: str
    created_at: datetime
    overall_status: OverallStatus
    steps: dict[JobStepKey, StepState] = Field(default_factory=dict)
    outputs: dict[str, Any] = Field(default_factory=dict)


def _get_job_record_path(*, user_id: str, job_id: str) -> Path:
    root = get_job_root(user_id=user_id, job_id=job_id)
    return root / "job.json"


def _read_job_record(*, user_id: str, job_id: str) -> PersistedJobRecord | None:
    path = _get_job_record_path(user_id=user_id, job_id=job_id)
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
        return PersistedJobRecord.model_validate(raw)
    except (OSError, json.JSONDecodeError, ValueError):
        return None


def _write_job_record(record: PersistedJobRecord) -> None:
    path = _get_job_record_path(user_id=record.user_id, job_id=record.job_id)
    ensure_dir(path.parent)
    path.write_text(record.model_dump_json(indent=2), encoding="utf-8")


class InMemoryJobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, JobRecord] = {}

    def create_job(self, *, user_id: str) -> JobRecord:
        job_id = uuid.uuid4().hex
        created_at = datetime.now(timezone.utc)

        steps: dict[JobStepKey, StepState] = {
            "silence_removal": "pending",
            "best_take": "pending",
            "captions": "pending",
            "export": "pending",
        }

        record = JobRecord(
            job_id=job_id,
            user_id=user_id,
            created_at=created_at,
            overall_status="queued",
            steps=steps,
        )
        self._jobs[job_id] = record
        self.save_job(record)
        return record

    def get_job(self, *, job_id: str, user_id: str) -> JobRecord | None:
        record = self._jobs.get(job_id)
        if not record:
            persisted = _read_job_record(user_id=user_id, job_id=job_id)
            if persisted is None:
                return None
            record = JobRecord(
                job_id=persisted.job_id,
                user_id=persisted.user_id,
                created_at=persisted.created_at,
                overall_status=persisted.overall_status,
                steps=dict(persisted.steps),
                outputs=dict(persisted.outputs),
            )
            self._jobs[job_id] = record
        if record.user_id != user_id:
            return None
        return record

    def save_job(self, record: JobRecord) -> None:
        _write_job_record(record.to_persisted())

    def find_job_owner(self, *, job_id: str) -> str | None:
        """
        Best-effort lookup for "this job exists but belongs to another user".

        Used only for returning 403 instead of a misleading 404.
        """

        try:
            if not UPLOADS_ROOT.exists():
                return None
            for user_dir in UPLOADS_ROOT.iterdir():
                if not user_dir.is_dir():
                    continue
                candidate = user_dir / job_id / "job.json"
                if candidate.exists():
                    return user_dir.name
        except OSError:
            return None
        return None

    def to_response(self, record: JobRecord) -> JobResponse:
        return JobResponse(
            job_id=record.job_id,
            created_at=record.created_at.isoformat(),
            overall_status=record.overall_status,
            steps=record.steps,
            outputs=record.outputs,
        )


job_store = InMemoryJobStore()


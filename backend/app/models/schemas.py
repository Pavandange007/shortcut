from typing import Any, Literal
from pydantic import BaseModel, Field

StepState = Literal["pending", "running", "done", "failed"]
OverallStatus = Literal["queued", "running", "completed", "failed"]

JobStepKey = Literal["silence_removal", "best_take", "captions", "export"]


class JobCreateResponse(BaseModel):
    job_id: str


class JobResponse(BaseModel):
    job_id: str
    created_at: str
    overall_status: OverallStatus
    steps: dict[JobStepKey, StepState] = Field(
        default_factory=dict,
        description="Per-step states used by the frontend pipeline UI.",
    )
    outputs: dict[str, Any] = Field(default_factory=dict)


class JobUploadResponse(BaseModel):
    job_id: str
    status: OverallStatus


class HealthResponse(BaseModel):
    ok: bool = True
    version: str = "0.1.0"
    ffmpeg_available: bool = False
    ffmpeg_path: str | None = None


class WordTiming(BaseModel):
    text: str
    start_ms: int
    end_ms: int
    confidence: float | None = None
    segment_index: int


class TranscriptResponse(BaseModel):
    words: list[WordTiming]
    raw_text: str


class SilenceSegment(BaseModel):
    start_ms: int
    end_ms: int


class TimelineSegment(BaseModel):
    start_ms: int
    end_ms: int
    keep_audio: bool
    crossfade_to_next_ms: int | None = None


class SilenceTimelineResponse(BaseModel):
    timeline: list[TimelineSegment]


class BestTakeRequest(BaseModel):
    takes: list[str] = Field(min_length=1, description="Multiple transcript takes for the same scene.")


class BestTakeResponse(BaseModel):
    best_index: int
    explanation: str


class CaptionLine(BaseModel):
    start_ms: int
    end_ms: int
    text: str
    words: list[WordTiming]


class CaptionsRequest(BaseModel):
    burn_in: bool = False
    max_chars: int = 42
    max_duration_ms: int = 2400


class CaptionsResponse(BaseModel):
    captions: list[CaptionLine]
    burned_captions_url: str | None = None


class ExportRequest(BaseModel):
    crossfade_ms: int = 150


class ExportResponse(BaseModel):
    rough_cut_url: str


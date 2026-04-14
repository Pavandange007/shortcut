from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator

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
    outputs: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Arbitrary job payload for the UI. Includes media URLs, errors, and multi-agent "
            "fields: contentAnalysis, storyAnalysis, viralAnalysis, titleHookAnalysis, "
            "refinement, agentOrchestration, agentTrace, userFeedback."
        ),
    )


class JobUploadResponse(BaseModel):
    job_id: str
    status: OverallStatus


class HealthResponse(BaseModel):
    ok: bool = True
    version: str = "0.1.0"
    ffmpeg_available: bool = False
    ffmpeg_path: str | None = None
    gemini_configured: bool = False
    gemini_agent_model: str | None = None
    gemini_api_key_hint: str | None = None
    llm_provider: str = "gemini"
    ollama_base_url: str | None = None
    ollama_model: str | None = None


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
    """Timeline segment; disk JSON uses snake_case via model_dump without by_alias."""

    model_config = ConfigDict(populate_by_name=True)

    start_ms: int = Field(
        serialization_alias="startMs",
        validation_alias=AliasChoices("start_ms", "startMs"),
    )
    end_ms: int = Field(
        serialization_alias="endMs",
        validation_alias=AliasChoices("end_ms", "endMs"),
    )
    keep_audio: bool = Field(
        serialization_alias="keepAudio",
        validation_alias=AliasChoices("keep_audio", "keepAudio"),
    )
    crossfade_to_next_ms: int | None = Field(
        default=None,
        serialization_alias="crossfadeToNextMs",
        validation_alias=AliasChoices("crossfade_to_next_ms", "crossfadeToNextMs"),
    )


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


# --- Multi-agent (Phase 1+) — persisted in job outputs and agent JSON artifacts ---


class MomentSpan(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    start_ms: int = Field(serialization_alias="startMs")
    end_ms: int = Field(serialization_alias="endMs")
    label: str = ""
    impact_score: float = Field(ge=0.0, le=1.0, serialization_alias="impactScore")
    evidence: str = ""


class ContentAnalysisResult(BaseModel):
    """Structured output from the Content Analyzer agent."""

    moments: list[MomentSpan] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    summary: str = ""


class AgentTraceEntry(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    agent: str
    ts: str
    confidence: float | None = None
    summary: str = ""
    inputs_hash: str | None = Field(default=None, serialization_alias="inputsHash")
    cache_hit: bool = Field(default=False, serialization_alias="cacheHit")


StoryBeatRole = Literal["setup", "tension", "payoff", "cta", "other"]


class StoryBeat(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    start_ms: int = Field(
        serialization_alias="startMs",
        validation_alias=AliasChoices("start_ms", "startMs"),
    )
    end_ms: int = Field(
        serialization_alias="endMs",
        validation_alias=AliasChoices("end_ms", "endMs"),
    )
    role: StoryBeatRole = "other"
    summary: str = ""
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)

    @field_validator("role", mode="before")
    @classmethod
    def _normalize_role(cls, v: object) -> str:
        if isinstance(v, str):
            x = v.strip().lower()
            if x in ("setup", "tension", "payoff", "cta", "other"):
                return x
        return "other"


class StoryAnalysisResult(BaseModel):
    beats: list[StoryBeat] = Field(default_factory=list)
    narrative_summary: str = Field(default="", serialization_alias="narrativeSummary")
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)


class ViralClip(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    start_ms: int = Field(
        serialization_alias="startMs",
        validation_alias=AliasChoices("start_ms", "startMs"),
    )
    end_ms: int = Field(
        serialization_alias="endMs",
        validation_alias=AliasChoices("end_ms", "endMs"),
    )
    viral_score: float = Field(
        ge=0.0,
        le=1.0,
        serialization_alias="viralScore",
        validation_alias=AliasChoices("viral_score", "viralScore"),
    )
    rationale: str = ""
    platform_recommendations: list[str] = Field(
        default_factory=list,
        serialization_alias="platformRecommendations",
        validation_alias=AliasChoices("platform_recommendations", "platformRecommendations"),
    )


class ViralAnalysisResult(BaseModel):
    clips: list[ViralClip] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)


class TitleHookSet(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    primary_title: str = Field(
        default="",
        serialization_alias="primaryTitle",
        validation_alias=AliasChoices("primary_title", "primaryTitle"),
    )
    hooks: list[str] = Field(default_factory=list)
    ab_variants: list[str] = Field(
        default_factory=list,
        serialization_alias="abVariants",
        validation_alias=AliasChoices("ab_variants", "abVariants"),
    )


class ClipTitleHooks(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    clip_index: int = Field(
        serialization_alias="clipIndex",
        validation_alias=AliasChoices("clip_index", "clipIndex"),
    )
    title_hook_set: TitleHookSet = Field(
        serialization_alias="titleHookSet",
        validation_alias=AliasChoices("title_hook_set", "titleHookSet"),
    )


class TitleHookAnalysisResult(BaseModel):
    clips: list[ClipTitleHooks] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)


class QualityReport(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    pacing: float = Field(ge=0.0, le=1.0, default=0.5)
    clarity: float = Field(ge=0.0, le=1.0, default=0.5)
    hook_strength: float = Field(
        ge=0.0,
        le=1.0,
        default=0.5,
        serialization_alias="hookStrength",
        validation_alias=AliasChoices("hook_strength", "hookStrength"),
    )
    redundancy: float = Field(ge=0.0, le=1.0, default=0.5)
    recommendations: list[str] = Field(default_factory=list)


class RefinementIteration(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    iteration_index: int = Field(serialization_alias="iterationIndex")
    timeline_delta_summary: str = Field(default="", serialization_alias="timelineDeltaSummary")
    quality_before: float = Field(ge=0.0, le=1.0, serialization_alias="qualityBefore")
    quality_after: float = Field(ge=0.0, le=1.0, serialization_alias="qualityAfter")


class RefinementResult(BaseModel):
    """Single refinement agent pass output."""

    model_config = ConfigDict(populate_by_name=True)

    timeline: list[TimelineSegment] = Field(default_factory=list)
    quality: QualityReport = Field(default_factory=QualityReport)
    overall_quality_score: float = Field(
        ge=0.0,
        le=1.0,
        default=0.5,
        serialization_alias="overallQualityScore",
        validation_alias=AliasChoices("overall_quality_score", "overallQualityScore"),
    )
    should_continue: bool = Field(
        default=False,
        serialization_alias="shouldContinue",
        validation_alias=AliasChoices("should_continue", "shouldContinue"),
    )
    summary: str = ""


class RefinementJobOutput(BaseModel):
    """Stored under job.outputs['refinement'] after the refinement loop."""

    model_config = ConfigDict(populate_by_name=True)

    iterations: list[RefinementIteration] = Field(default_factory=list)
    final_quality_score: float = Field(
        ge=0.0,
        le=1.0,
        default=0.0,
        serialization_alias="finalQualityScore",
    )
    converged: bool = False
    confidence: float | None = None
    summary: str = ""
    max_iterations: int = Field(default=3, serialization_alias="maxIterations")
    last_quality: QualityReport | None = Field(default=None, serialization_alias="lastQuality")


class JobFeedbackRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    notes: str = ""
    audience: str = ""
    style: str = ""
    must_include_ms: list[int] = Field(default_factory=list, serialization_alias="mustIncludeMs")
    must_exclude_ms: list[int] = Field(default_factory=list, serialization_alias="mustExcludeMs")


class JobFeedbackResponse(BaseModel):
    job_id: str
    ok: bool = True


ChatRole = Literal["user", "assistant"]
ChatMessageStatus = Literal["queued", "running", "done", "error"]


class JobChatMessage(BaseModel):
    """Persisted chat message stored under job outputs."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    role: ChatRole
    text: str
    created_at: str = Field(serialization_alias="createdAt")
    status: ChatMessageStatus = "done"
    error: str | None = None


class JobChatRequest(BaseModel):
    """User sends a chat message to control agents."""

    message: str = Field(min_length=1, max_length=4000)


class JobChatResponse(BaseModel):
    job_id: str
    accepted: bool = True
    user_message_id: str = Field(serialization_alias="userMessageId")
    assistant_message_id: str = Field(serialization_alias="assistantMessageId")


class AgentOrchestrationState(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    phase: str = ""
    active_agents: list[str] = Field(default_factory=list, serialization_alias="activeAgents")
    last_messages: list[dict[str, object]] = Field(
        default_factory=list,
        serialization_alias="lastMessages",
    )
    refinement_iteration: int | None = Field(default=None, serialization_alias="refinementIteration")
    max_refinement_iterations: int | None = Field(
        default=None,
        serialization_alias="maxRefinementIterations",
    )
    refinement_converged: bool | None = Field(default=None, serialization_alias="refinementConverged")
    final_quality_score: float | None = Field(default=None, serialization_alias="finalQualityScore")


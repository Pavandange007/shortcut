from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Generic, TypeVar

from app.models.schemas import (
    ContentAnalysisResult,
    StoryAnalysisResult,
    TimelineSegment,
    TitleHookAnalysisResult,
    TranscriptResponse,
    ViralAnalysisResult,
    WordTiming,
)

TOut = TypeVar("TOut")


@dataclass
class AgentContext:
    user_id: str
    job_id: str
    transcript: TranscriptResponse
    words: list[WordTiming]
    agents_dir: Path
    cache_dir: Path
    content_analysis: ContentAnalysisResult | None = None
    story_analysis: StoryAnalysisResult | None = None
    viral_analysis: ViralAnalysisResult | None = None
    title_analysis: TitleHookAnalysisResult | None = None
    baseline_timeline: list[TimelineSegment] = field(default_factory=list)
    current_timeline: list[TimelineSegment] = field(default_factory=list)
    refinement_iteration: int = 0
    user_feedback: dict[str, Any] | None = None


@dataclass
class AgentResult(Generic[TOut]):
    name: str
    payload: TOut
    confidence: float | None
    summary: str
    cache_hit: bool
    inputs_hash: str


class BaseAgent(ABC, Generic[TOut]):
    """Specialized agent: structured input via AgentContext, structured output + trace metadata."""

    @property
    @abstractmethod
    def agent_name(self) -> str: ...

    @abstractmethod
    def process(self, ctx: AgentContext) -> AgentResult[TOut]: ...

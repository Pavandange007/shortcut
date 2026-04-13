from __future__ import annotations

import hashlib
import json
import logging

from app.models.schemas import ContentAnalysisResult, StoryAnalysisResult, StoryBeat
from app.prompts.story_structure_prompt import (
    STORY_STRUCTURE_PROMPT_VERSION,
    build_story_structure_prompt,
)
from app.services.agent_cache import (
    build_agent_inputs_hash,
    cache_json_path,
    read_cached_model,
    write_cached_payload,
)
from app.services.agents.base import AgentContext, AgentResult, BaseAgent
from app.services.gemini_service import generate_agent_json

logger = logging.getLogger(__name__)


def _story_suffix(content: ContentAnalysisResult) -> str:
    blob = json.dumps(
        [m.model_dump(mode="json") for m in content.moments],
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(
        f"{STORY_STRUCTURE_PROMPT_VERSION}|{blob}".encode("utf-8")
    ).hexdigest()


def heuristic_story_fallback(ctx: AgentContext, content: ContentAnalysisResult) -> StoryAnalysisResult:
    words = ctx.words
    if not words:
        return StoryAnalysisResult(
            beats=[],
            narrative_summary="No transcript.",
            confidence=0.2,
        )
    start = words[0].start_ms
    end = words[-1].end_ms
    beats = [
        StoryBeat(
            start_ms=start,
            end_ms=end,
            role="other",
            summary="Full take (heuristic fallback).",
            confidence=0.35,
        )
    ]
    if content.moments:
        beats.insert(
            0,
            StoryBeat(
                start_ms=content.moments[0].start_ms,
                end_ms=min(content.moments[0].end_ms, end),
                role="setup",
                summary="Opening hook region from content analysis.",
                confidence=0.4,
            ),
        )
    return StoryAnalysisResult(
        beats=beats,
        narrative_summary="Heuristic story structure (Gemini unavailable or failed).",
        confidence=0.35,
    )


class StoryStructureAgent(BaseAgent[StoryAnalysisResult]):
    @property
    def agent_name(self) -> str:
        return "story_structure"

    def process(self, ctx: AgentContext) -> AgentResult[StoryAnalysisResult]:
        content = ctx.content_analysis or ContentAnalysisResult()
        fp = _transcript_fingerprint_short(ctx.transcript.raw_text, ctx.words)
        suffix = _story_suffix(content)
        inputs_hash = build_agent_inputs_hash(
            agent_name=self.agent_name,
            transcript_fingerprint=fp,
            suffix=suffix,
        )
        cache_path = cache_json_path(ctx.cache_dir, inputs_hash)

        cached = read_cached_model(cache_path, StoryAnalysisResult)
        if cached is not None:
            return AgentResult(
                name=self.agent_name,
                payload=cached,
                confidence=cached.confidence,
                summary=cached.narrative_summary[:500] or "Cached story analysis.",
                cache_hit=True,
                inputs_hash=inputs_hash,
            )

        prompt = build_story_structure_prompt(
            raw_text=ctx.transcript.raw_text,
            transcript=ctx.transcript,
            content=content,
        )
        try:
            parsed = generate_agent_json(prompt=prompt, response_model=StoryAnalysisResult)
            write_cached_payload(cache_path, parsed.model_dump(mode="json"))
            return AgentResult(
                name=self.agent_name,
                payload=parsed,
                confidence=parsed.confidence,
                summary=parsed.narrative_summary[:500] or "Story structure complete.",
                cache_hit=False,
                inputs_hash=inputs_hash,
            )
        except Exception as e:
            logger.warning("%s: Gemini failed (%s); using heuristic.", self.agent_name, e)
            fallback = heuristic_story_fallback(ctx, content)
            write_cached_payload(cache_path, fallback.model_dump(mode="json"))
            return AgentResult(
                name=self.agent_name,
                payload=fallback,
                confidence=fallback.confidence,
                summary=fallback.narrative_summary,
                cache_hit=False,
                inputs_hash=inputs_hash,
            )


def _transcript_fingerprint_short(raw_text: str, words) -> str:
    body = raw_text.encode("utf-8", errors="replace")[:8000]
    tail = f"|{len(words)}"
    h = hashlib.sha256()
    h.update(body)
    h.update(tail.encode("utf-8"))
    return h.hexdigest()

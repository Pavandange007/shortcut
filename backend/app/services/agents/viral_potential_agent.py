from __future__ import annotations

import hashlib
import json
import logging

from app.models.schemas import (
    ContentAnalysisResult,
    StoryAnalysisResult,
    ViralAnalysisResult,
    ViralClip,
)
from app.prompts.viral_potential_prompt import (
    VIRAL_POTENTIAL_PROMPT_VERSION,
    build_viral_potential_prompt,
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


def _viral_suffix(content: ContentAnalysisResult, story: StoryAnalysisResult) -> str:
    blob = json.dumps(
        {
            "m": [m.model_dump(mode="json") for m in content.moments],
            "b": [b.model_dump(mode="json") for b in story.beats],
            "s": story.narrative_summary,
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(
        f"{VIRAL_POTENTIAL_PROMPT_VERSION}|{blob}".encode("utf-8")
    ).hexdigest()


def heuristic_viral_fallback(content: ContentAnalysisResult) -> ViralAnalysisResult:
    clips: list[ViralClip] = []
    for m in content.moments[:6]:
        clips.append(
            ViralClip(
                start_ms=m.start_ms,
                end_ms=m.end_ms,
                viral_score=min(1.0, max(0.0, m.impact_score)),
                rationale="Derived from content-analysis moment (heuristic).",
                platform_recommendations=["shorts", "reels", "tiktok"],
            )
        )
    return ViralAnalysisResult(
        clips=clips,
        confidence=0.35,
    )


class ViralPotentialAgent(BaseAgent[ViralAnalysisResult]):
    @property
    def agent_name(self) -> str:
        return "viral_potential"

    def process(self, ctx: AgentContext) -> AgentResult[ViralAnalysisResult]:
        content = ctx.content_analysis or ContentAnalysisResult()
        story = ctx.story_analysis or StoryAnalysisResult()
        fp = _transcript_fp(ctx.transcript.raw_text, ctx.words)
        suffix = _viral_suffix(content, story)
        inputs_hash = build_agent_inputs_hash(
            agent_name=self.agent_name,
            transcript_fingerprint=fp,
            suffix=suffix,
        )
        cache_path = cache_json_path(ctx.cache_dir, inputs_hash)

        cached = read_cached_model(cache_path, ViralAnalysisResult)
        if cached is not None:
            return AgentResult(
                name=self.agent_name,
                payload=cached,
                confidence=cached.confidence,
                summary=f"{len(cached.clips)} clip candidates (cached).",
                cache_hit=True,
                inputs_hash=inputs_hash,
            )

        prompt = build_viral_potential_prompt(content=content, story=story)
        try:
            parsed = generate_agent_json(prompt=prompt, response_model=ViralAnalysisResult)
            write_cached_payload(cache_path, parsed.model_dump(mode="json"))
            return AgentResult(
                name=self.agent_name,
                payload=parsed,
                confidence=parsed.confidence,
                summary=f"{len(parsed.clips)} viral clip candidates.",
                cache_hit=False,
                inputs_hash=inputs_hash,
            )
        except Exception as e:
            logger.warning("%s: Gemini failed (%s); using heuristic.", self.agent_name, e)
            fallback = heuristic_viral_fallback(content)
            write_cached_payload(cache_path, fallback.model_dump(mode="json"))
            return AgentResult(
                name=self.agent_name,
                payload=fallback,
                confidence=fallback.confidence,
                summary="Heuristic viral clips from content moments.",
                cache_hit=False,
                inputs_hash=inputs_hash,
            )


def _transcript_fp(raw_text: str, words) -> str:
    body = raw_text.encode("utf-8", errors="replace")[:8000]
    h = hashlib.sha256()
    h.update(body)
    h.update(str(len(words)).encode("utf-8"))
    return h.hexdigest()

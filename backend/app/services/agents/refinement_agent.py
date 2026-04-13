from __future__ import annotations

import hashlib
import json
import logging

from app.models.schemas import (
    ContentAnalysisResult,
    QualityReport,
    RefinementResult,
    StoryAnalysisResult,
    TimelineSegment,
    TitleHookAnalysisResult,
    ViralAnalysisResult,
)
from app.prompts.refinement_prompt import (
    REFINEMENT_PROMPT_VERSION,
    build_refinement_prompt,
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


def coerce_refinement_timeline(
    baseline: list[TimelineSegment],
    proposed: list[TimelineSegment],
) -> list[TimelineSegment]:
    if len(proposed) != len(baseline):
        logger.warning(
            "refinement: timeline length mismatch (baseline=%d proposed=%d); keeping baseline.",
            len(baseline),
            len(proposed),
        )
        return [TimelineSegment.model_validate(s.model_dump(mode="json")) for s in baseline]

    out: list[TimelineSegment] = []
    for b, p in zip(baseline, proposed, strict=True):
        if b.start_ms != p.start_ms or b.end_ms != p.end_ms:
            out.append(b)
            continue
        out.append(
            TimelineSegment(
                start_ms=b.start_ms,
                end_ms=b.end_ms,
                keep_audio=p.keep_audio,
                crossfade_to_next_ms=p.crossfade_to_next_ms,
            )
        )
    return out


def _heuristic_refinement(baseline: list[TimelineSegment]) -> RefinementResult:
    return RefinementResult(
        timeline=[TimelineSegment.model_validate(s.model_dump(mode="json")) for s in baseline],
        quality=QualityReport(
            pacing=0.55,
            clarity=0.55,
            hook_strength=0.5,
            redundancy=0.45,
            recommendations=["Heuristic pass: timeline unchanged (Gemini unavailable or failed)."],
        ),
        overall_quality_score=0.52,
        should_continue=False,
        summary="Baseline timeline preserved.",
    )


def _refinement_suffix(
    iteration_index: int,
    timeline: list[TimelineSegment],
    content: ContentAnalysisResult,
    story: StoryAnalysisResult,
    viral: ViralAnalysisResult,
) -> str:
    tl_sig = json.dumps(
        [(s.keep_audio, s.crossfade_to_next_ms) for s in timeline],
        ensure_ascii=False,
    )
    blob = json.dumps(
        {
            "i": iteration_index,
            "tl": tl_sig,
            "m": len(content.moments),
            "b": len(story.beats),
            "v": len(viral.clips),
            "v_prompt": REFINEMENT_PROMPT_VERSION,
        },
        sort_keys=True,
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


class RefinementAgent(BaseAgent[RefinementResult]):
    @property
    def agent_name(self) -> str:
        return "refinement"

    def process(self, ctx: AgentContext) -> AgentResult[RefinementResult]:
        baseline = ctx.current_timeline or ctx.baseline_timeline
        if not baseline:
            empty = _heuristic_refinement([])
            return AgentResult(
                name=self.agent_name,
                payload=empty,
                confidence=0.2,
                summary="No timeline to refine.",
                cache_hit=False,
                inputs_hash="",
            )

        content = ctx.content_analysis or ContentAnalysisResult()
        story = ctx.story_analysis or StoryAnalysisResult()
        viral = ctx.viral_analysis or ViralAnalysisResult()
        titles = ctx.title_analysis

        fp = _transcript_fp(ctx.transcript.raw_text, ctx.words)
        suffix = _refinement_suffix(ctx.refinement_iteration, baseline, content, story, viral)
        inputs_hash = build_agent_inputs_hash(
            agent_name=f"{self.agent_name}_{ctx.refinement_iteration}",
            transcript_fingerprint=fp,
            suffix=suffix,
        )
        cache_path = cache_json_path(ctx.cache_dir, inputs_hash)

        cached = read_cached_model(cache_path, RefinementResult)
        if cached is not None:
            merged = RefinementResult(
                timeline=coerce_refinement_timeline(baseline, cached.timeline),
                quality=cached.quality,
                overall_quality_score=cached.overall_quality_score,
                should_continue=cached.should_continue,
                summary=cached.summary,
            )
            return AgentResult(
                name=self.agent_name,
                payload=merged,
                confidence=cached.overall_quality_score,
                summary=cached.summary[:500],
                cache_hit=True,
                inputs_hash=inputs_hash,
            )

        prompt = build_refinement_prompt(
            iteration_index=ctx.refinement_iteration,
            timeline=baseline,
            content=content,
            story=story,
            viral=viral,
            titles=titles,
            user_feedback=ctx.user_feedback,
        )
        try:
            parsed = generate_agent_json(prompt=prompt, response_model=RefinementResult)
            merged_timeline = coerce_refinement_timeline(baseline, parsed.timeline)
            merged = RefinementResult(
                timeline=merged_timeline,
                quality=parsed.quality,
                overall_quality_score=parsed.overall_quality_score,
                should_continue=parsed.should_continue,
                summary=parsed.summary,
            )
            # Cache the merged (valid) result shape
            write_cached_payload(cache_path, merged.model_dump(mode="json", by_alias=True))
            return AgentResult(
                name=self.agent_name,
                payload=merged,
                confidence=merged.overall_quality_score,
                summary=merged.summary[:500] or "Refinement step complete.",
                cache_hit=False,
                inputs_hash=inputs_hash,
            )
        except Exception as e:
            logger.warning("%s: Gemini failed (%s); using heuristic.", self.agent_name, e)
            fallback = _heuristic_refinement(baseline)
            write_cached_payload(cache_path, fallback.model_dump(mode="json", by_alias=True))
            return AgentResult(
                name=self.agent_name,
                payload=fallback,
                confidence=fallback.overall_quality_score,
                summary=fallback.summary,
                cache_hit=False,
                inputs_hash=inputs_hash,
            )


def _transcript_fp(raw_text: str, words) -> str:
    body = raw_text.encode("utf-8", errors="replace")[:8000]
    h = hashlib.sha256()
    h.update(body)
    h.update(str(len(words)).encode("utf-8"))
    return h.hexdigest()

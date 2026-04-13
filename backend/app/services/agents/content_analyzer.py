from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

from app.models.schemas import ContentAnalysisResult, MomentSpan, TranscriptResponse, WordTiming
from app.prompts.content_analysis_prompt import build_content_analysis_prompt
from app.services.agent_cache import (
    build_agent_inputs_hash,
    cache_json_path,
    read_cached_model,
    write_cached_payload,
)
from app.services.agents.base import AgentContext, AgentResult, BaseAgent
from app.services.gemini_service import generate_agent_json

logger = logging.getLogger(__name__)


def _transcript_fingerprint(raw_text: str, words: list[WordTiming]) -> str:
    body = raw_text.encode("utf-8", errors="replace")[:12000]
    tail = f"|{len(words)}|{words[0].start_ms if words else 0}|{words[-1].end_ms if words else 0}"
    h = hashlib.sha256()
    h.update(body)
    h.update(tail.encode("utf-8"))
    return h.hexdigest()


def _heuristic_moments(words: list[WordTiming]) -> ContentAnalysisResult:
    if not words:
        return ContentAnalysisResult(
            moments=[],
            confidence=0.2,
            summary="No transcript words; heuristic skipped.",
        )

    last_ms = max(w.end_ms for w in words)
    bucket_ms = 10_000
    counts: dict[int, int] = {}
    for w in words:
        b = w.start_ms // bucket_ms
        counts[b] = counts.get(b, 0) + 1

    top_buckets = sorted(counts.items(), key=lambda kv: -kv[1])[:8]
    moments: list[MomentSpan] = []
    for b, cnt in sorted(top_buckets, key=lambda kv: kv[0]):
        start_ms = b * bucket_ms
        end_ms = min(start_ms + bucket_ms, last_ms + 200)
        wps = cnt / max(bucket_ms / 1000.0, 0.001)
        impact = min(1.0, wps / 5.5)
        moments.append(
            MomentSpan(
                start_ms=start_ms,
                end_ms=end_ms,
                label="High speech density",
                impact_score=round(impact, 3),
                evidence=f"~{cnt} words in ~{bucket_ms // 1000}s window",
            )
        )

    return ContentAnalysisResult(
        moments=moments,
        confidence=0.35,
        summary="Heuristic density-based moments (Gemini unavailable or failed).",
    )


class ContentAnalyzerAgent(BaseAgent[ContentAnalysisResult]):
    @property
    def agent_name(self) -> str:
        return "content_analyzer"

    def process(self, ctx: AgentContext) -> AgentResult[ContentAnalysisResult]:
        raw = ctx.transcript.raw_text
        words = ctx.words
        fp = _transcript_fingerprint(raw, words)
        inputs_hash = build_agent_inputs_hash(agent_name=self.agent_name, transcript_fingerprint=fp)
        cache_path = cache_json_path(ctx.cache_dir, inputs_hash)

        cached = read_cached_model(cache_path, ContentAnalysisResult)
        if cached is not None:
            return AgentResult(
                name=self.agent_name,
                payload=cached,
                confidence=cached.confidence,
                summary=cached.summary or "Cached content analysis.",
                cache_hit=True,
                inputs_hash=inputs_hash,
            )

        prompt = build_content_analysis_prompt(raw_text=raw, words=words)
        try:
            parsed = generate_agent_json(prompt=prompt, response_model=ContentAnalysisResult)
            write_cached_payload(cache_path, parsed.model_dump(mode="json"))
            return AgentResult(
                name=self.agent_name,
                payload=parsed,
                confidence=parsed.confidence,
                summary=parsed.summary or "Content analysis complete.",
                cache_hit=False,
                inputs_hash=inputs_hash,
            )
        except Exception as e:
            logger.warning("%s: Gemini failed (%s); using heuristic.", self.agent_name, e)
            fallback = _heuristic_moments(words)
            write_cached_payload(cache_path, fallback.model_dump(mode="json"))
            return AgentResult(
                name=self.agent_name,
                payload=fallback,
                confidence=fallback.confidence,
                summary=fallback.summary,
                cache_hit=False,
                inputs_hash=inputs_hash,
            )


def run_content_analyzer(ctx: AgentContext) -> AgentResult[ContentAnalysisResult]:
    return ContentAnalyzerAgent().process(ctx)


def context_from_transcript(
    *,
    user_id: str,
    job_id: str,
    transcript: TranscriptResponse,
    agents_dir: Path,
    cache_dir: Path,
) -> AgentContext:
    return AgentContext(
        user_id=user_id,
        job_id=job_id,
        transcript=transcript,
        words=list(transcript.words),
        agents_dir=agents_dir,
        cache_dir=cache_dir,
    )

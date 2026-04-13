from __future__ import annotations

import hashlib
import json
import logging

from app.models.schemas import (
    ClipTitleHooks,
    TitleHookAnalysisResult,
    TitleHookSet,
    ViralAnalysisResult,
)
from app.prompts.title_hook_prompt import (
    TITLE_HOOK_PROMPT_VERSION,
    build_title_hook_prompt,
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


def _title_suffix(viral: ViralAnalysisResult) -> str:
    blob = json.dumps(
        [c.model_dump(mode="json", by_alias=True) for c in viral.clips],
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(
        f"{TITLE_HOOK_PROMPT_VERSION}|{blob}".encode("utf-8")
    ).hexdigest()


def heuristic_title_fallback(viral: ViralAnalysisResult, raw_text: str) -> TitleHookAnalysisResult:
    base = (raw_text.strip()[:72] or "Your next clip").replace("\n", " ")
    clips: list[ClipTitleHooks] = []
    for i, c in enumerate(viral.clips):
        clips.append(
            ClipTitleHooks(
                clip_index=i,
                title_hook_set=TitleHookSet(
                    primary_title=base,
                    hooks=[base, "Watch until the end."],
                    ab_variants=[base[:50], base[:40] + "…"],
                ),
            )
        )
    return TitleHookAnalysisResult(clips=clips, confidence=0.3)


class TitleHookAgent(BaseAgent[TitleHookAnalysisResult]):
    @property
    def agent_name(self) -> str:
        return "title_hook"

    def process(self, ctx: AgentContext) -> AgentResult[TitleHookAnalysisResult]:
        viral = ctx.viral_analysis or ViralAnalysisResult()
        if not viral.clips:
            empty = TitleHookAnalysisResult(clips=[], confidence=0.2)
            return AgentResult(
                name=self.agent_name,
                payload=empty,
                confidence=0.2,
                summary="No viral clips to title.",
                cache_hit=False,
                inputs_hash="",
            )

        fp = _transcript_fp(ctx.transcript.raw_text, ctx.words)
        suffix = _title_suffix(viral)
        inputs_hash = build_agent_inputs_hash(
            agent_name=self.agent_name,
            transcript_fingerprint=fp,
            suffix=suffix,
        )
        cache_path = cache_json_path(ctx.cache_dir, inputs_hash)

        cached = read_cached_model(cache_path, TitleHookAnalysisResult)
        if cached is not None:
            return AgentResult(
                name=self.agent_name,
                payload=cached,
                confidence=cached.confidence,
                summary=f"{len(cached.clips)} clip title sets (cached).",
                cache_hit=True,
                inputs_hash=inputs_hash,
            )

        prompt = build_title_hook_prompt(viral=viral)
        try:
            parsed = generate_agent_json(prompt=prompt, response_model=TitleHookAnalysisResult)
            write_cached_payload(cache_path, parsed.model_dump(mode="json"))
            return AgentResult(
                name=self.agent_name,
                payload=parsed,
                confidence=parsed.confidence,
                summary=f"{len(parsed.clips)} title/hook sets.",
                cache_hit=False,
                inputs_hash=inputs_hash,
            )
        except Exception as e:
            logger.warning("%s: Gemini failed (%s); using heuristic.", self.agent_name, e)
            fallback = heuristic_title_fallback(viral, ctx.transcript.raw_text)
            write_cached_payload(cache_path, fallback.model_dump(mode="json"))
            return AgentResult(
                name=self.agent_name,
                payload=fallback,
                confidence=fallback.confidence,
                summary="Heuristic titles from transcript excerpt.",
                cache_hit=False,
                inputs_hash=inputs_hash,
            )


def _transcript_fp(raw_text: str, words) -> str:
    body = raw_text.encode("utf-8", errors="replace")[:8000]
    h = hashlib.sha256()
    h.update(body)
    h.update(str(len(words)).encode("utf-8"))
    return h.hexdigest()

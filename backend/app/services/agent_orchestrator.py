from __future__ import annotations

import dataclasses
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import settings
from app.models.schemas import (
    AgentOrchestrationState,
    AgentTraceEntry,
    ContentAnalysisResult,
    RefinementIteration,
    RefinementJobOutput,
    StoryAnalysisResult,
    TimelineSegment,
    TitleHookAnalysisResult,
    TranscriptResponse,
    ViralAnalysisResult,
)
from app.services.agent_bus import get_message_bus
from app.services.agents.base import AgentContext, AgentResult
from app.services.agents.content_analyzer import (
    ContentAnalyzerAgent,
    _heuristic_moments,
    context_from_transcript,
)
from app.services.agents.refinement_agent import RefinementAgent
from app.services.agents.story_structure_agent import StoryStructureAgent, heuristic_story_fallback
from app.services.agents.title_hook_agent import TitleHookAgent, heuristic_title_fallback
from app.services.agents.viral_potential_agent import ViralPotentialAgent, heuristic_viral_fallback
from app.services.jobs_service import JobRecord
from app.storage.files import (
    get_agent_cache_dir,
    get_agent_messages_jsonl_path,
    get_agents_dir,
    get_content_analysis_json_path,
    get_refinement_iteration_json_path,
    get_refinement_summary_json_path,
    get_story_analysis_json_path,
    get_timeline_json_path,
    get_title_hook_analysis_json_path,
    get_viral_analysis_json_path,
)

logger = logging.getLogger(__name__)


def _append_jsonl(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def _append_trace(record: JobRecord, entry: AgentTraceEntry) -> None:
    tr = record.outputs.setdefault("agentTrace", [])
    if not isinstance(tr, list):
        tr = []
        record.outputs["agentTrace"] = tr
    tr.append(entry.model_dump(mode="json", by_alias=True))


def _load_timeline(path: Path) -> list[TimelineSegment]:
    raw = json.loads(path.read_text(encoding="utf-8-sig"))
    return [TimelineSegment.model_validate(item) for item in raw]


def _write_timeline(path: Path, segments: list[TimelineSegment]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps([s.model_dump(mode="json") for s in segments], ensure_ascii=False),
        encoding="utf-8",
    )


def _feedback_from_record(record: JobRecord) -> dict | None:
    fb = record.outputs.get("userFeedback")
    return fb if isinstance(fb, dict) else None


class AgentOrchestrator:
    """
    Coordinates specialized agents after ingest (transcript + baseline timeline).
    Runs analysis agents, then a bounded refinement loop that may rewrite timeline.json.
    """

    def run_story_structure_agent(self, ctx: AgentContext) -> AgentResult[StoryAnalysisResult]:
        return StoryStructureAgent().process(ctx)

    def run_viral_potential_agent(self, ctx: AgentContext) -> AgentResult[ViralAnalysisResult]:
        return ViralPotentialAgent().process(ctx)

    def run_title_hook_agent(self, ctx: AgentContext) -> AgentResult[TitleHookAnalysisResult]:
        return TitleHookAgent().process(ctx)

    def run_refinement_agent(self, ctx: AgentContext):
        return RefinementAgent().process(ctx)

    def run_post_transcript_agents(
        self,
        *,
        user_id: str,
        job_id: str,
        transcript: TranscriptResponse,
        record: JobRecord,
    ) -> None:
        bus = get_message_bus()
        agents_dir = get_agents_dir(user_id, job_id)
        cache_dir = get_agent_cache_dir(user_id, job_id)
        timeline_path = get_timeline_json_path(user_id, job_id)

        try:
            baseline = _load_timeline(timeline_path)
        except Exception as e:
            logger.warning("orchestrator: could not load timeline (%s); agent phase skipped.", e)
            record.outputs["agentPhaseError"] = f"timeline_load_failed: {e}"
            return

        ctx = context_from_transcript(
            user_id=user_id,
            job_id=job_id,
            transcript=transcript,
            agents_dir=agents_dir,
            cache_dir=cache_dir,
        )
        ctx = dataclasses.replace(
            ctx,
            baseline_timeline=list(baseline),
            current_timeline=list(baseline),
            user_feedback=_feedback_from_record(record),
        )

        bus.publish_simple(
            job_id=job_id,
            from_agent="orchestrator",
            type="phase_start",
            payload={"phase": "multi_agent"},
        )

        # --- Content analyzer (must not abort pipeline) ---
        try:
            ca_res = ContentAnalyzerAgent().process(ctx)
        except Exception:
            logger.exception("content_analyzer crashed user_id=%s job_id=%s", user_id, job_id)
            payload = _heuristic_moments(ctx.words)
            ca_res = AgentResult(
                name="content_analyzer",
                payload=payload,
                confidence=payload.confidence,
                summary=payload.summary,
                cache_hit=False,
                inputs_hash="",
            )

        ctx = dataclasses.replace(ctx, content_analysis=ca_res.payload)
        record.outputs["contentAnalysis"] = ca_res.payload.model_dump(mode="json", by_alias=True)
        self._persist_analysis_and_trace(
            user_id=user_id,
            job_id=job_id,
            record=record,
            bus=bus,
            result=ca_res,
            write_path=get_content_analysis_json_path(user_id, job_id),
            payload_dump=ca_res.payload.model_dump(mode="json"),
            bus_type="content_analysis_done",
            extra_bus={"momentCount": len(ca_res.payload.moments)},
        )

        # --- Story structure ---
        try:
            st_res = self.run_story_structure_agent(ctx)
        except Exception:
            logger.exception("story_structure crashed user_id=%s job_id=%s", user_id, job_id)
            sp = heuristic_story_fallback(ctx, ctx.content_analysis or ContentAnalysisResult())
            st_res = AgentResult(
                name="story_structure",
                payload=sp,
                confidence=sp.confidence,
                summary=sp.narrative_summary[:500],
                cache_hit=False,
                inputs_hash="",
            )

        ctx = dataclasses.replace(ctx, story_analysis=st_res.payload)
        self._persist_analysis_and_trace(
            user_id=user_id,
            job_id=job_id,
            record=record,
            bus=bus,
            result=st_res,
            write_path=get_story_analysis_json_path(user_id, job_id),
            payload_dump=st_res.payload.model_dump(mode="json"),
            bus_type="story_analysis_done",
            extra_bus={"beatCount": len(st_res.payload.beats)},
        )

        # --- Viral potential ---
        try:
            vi_res = self.run_viral_potential_agent(ctx)
        except Exception:
            logger.exception("viral_potential crashed user_id=%s job_id=%s", user_id, job_id)
            vp = heuristic_viral_fallback(ctx.content_analysis or ContentAnalysisResult())
            vi_res = AgentResult(
                name="viral_potential",
                payload=vp,
                confidence=vp.confidence,
                summary=f"{len(vp.clips)} clips (fallback).",
                cache_hit=False,
                inputs_hash="",
            )

        ctx = dataclasses.replace(ctx, viral_analysis=vi_res.payload)
        self._persist_analysis_and_trace(
            user_id=user_id,
            job_id=job_id,
            record=record,
            bus=bus,
            result=vi_res,
            write_path=get_viral_analysis_json_path(user_id, job_id),
            payload_dump=vi_res.payload.model_dump(mode="json"),
            bus_type="viral_analysis_done",
            extra_bus={"clipCount": len(vi_res.payload.clips)},
        )

        # --- Title / hook ---
        try:
            th_res = self.run_title_hook_agent(ctx)
        except Exception:
            logger.exception("title_hook crashed user_id=%s job_id=%s", user_id, job_id)
            tp = heuristic_title_fallback(
                ctx.viral_analysis or ViralAnalysisResult(),
                ctx.transcript.raw_text,
            )
            th_res = AgentResult(
                name="title_hook",
                payload=tp,
                confidence=tp.confidence,
                summary=f"{len(tp.clips)} title sets (fallback).",
                cache_hit=False,
                inputs_hash="",
            )

        ctx = dataclasses.replace(ctx, title_analysis=th_res.payload)
        self._persist_analysis_and_trace(
            user_id=user_id,
            job_id=job_id,
            record=record,
            bus=bus,
            result=th_res,
            write_path=get_title_hook_analysis_json_path(user_id, job_id),
            payload_dump=th_res.payload.model_dump(mode="json", by_alias=True),
            bus_type="title_hook_analysis_done",
            extra_bus={"titleClipCount": len(th_res.payload.clips)},
        )

        record.outputs["storyAnalysis"] = st_res.payload.model_dump(mode="json", by_alias=True)
        record.outputs["viralAnalysis"] = vi_res.payload.model_dump(mode="json", by_alias=True)
        record.outputs["titleHookAnalysis"] = th_res.payload.model_dump(mode="json", by_alias=True)

        # --- Refinement loop ---
        max_iter = max(1, min(settings.refinement_max_iterations, 5))
        threshold = settings.refinement_quality_threshold
        epsilon = settings.refinement_quality_epsilon

        current = list(ctx.current_timeline)
        iterations_out: list[RefinementIteration] = []
        prev_score = 0.0
        converged = False
        final_score = 0.0
        last_quality_report = None

        for i in range(max_iter):
            logger.info(
                "refinement iteration %d/%d user_id=%s job_id=%s",
                i + 1,
                max_iter,
                user_id,
                job_id,
            )
            ctx_loop = dataclasses.replace(
                ctx,
                current_timeline=list(current),
                refinement_iteration=i,
                user_feedback=_feedback_from_record(record),
            )
            try:
                rf_res = self.run_refinement_agent(ctx_loop)
            except Exception:
                logger.exception("refinement crashed user_id=%s job_id=%s iter=%d", user_id, job_id, i)
                break

            score = float(rf_res.payload.overall_quality_score)
            iterations_out.append(
                RefinementIteration(
                    iteration_index=i,
                    timeline_delta_summary=(rf_res.payload.summary or "")[:400],
                    quality_before=float(prev_score),
                    quality_after=score,
                )
            )
            iter_path = get_refinement_iteration_json_path(user_id, job_id, i)
            iter_path.write_text(
                json.dumps(rf_res.payload.model_dump(mode="json", by_alias=True), ensure_ascii=False),
                encoding="utf-8",
            )

            if rf_res.payload.timeline:
                current = list(rf_res.payload.timeline)

            last_quality_report = rf_res.payload.quality

            _append_trace(
                record,
                AgentTraceEntry(
                    agent=f"refinement_{i}",
                    ts=datetime.now(timezone.utc).isoformat(),
                    confidence=score,
                    summary=(rf_res.payload.summary or "")[:500],
                    inputs_hash=rf_res.inputs_hash,
                    cache_hit=rf_res.cache_hit,
                ),
            )

            final_score = score
            if score >= threshold:
                converged = True
                logger.info(
                    "refinement converged (threshold) user_id=%s job_id=%s score=%.3f",
                    user_id,
                    job_id,
                    score,
                )
                break
            if i > 0 and abs(score - prev_score) < epsilon:
                converged = True
                logger.info(
                    "refinement converged (epsilon) user_id=%s job_id=%s",
                    user_id,
                    job_id,
                )
                break
            if not rf_res.payload.should_continue and i > 0:
                converged = True
                logger.info(
                    "refinement stopped (should_continue=false) user_id=%s job_id=%s",
                    user_id,
                    job_id,
                )
                break
            prev_score = score

        _write_timeline(timeline_path, current)

        refinement_out = RefinementJobOutput(
            iterations=iterations_out,
            final_quality_score=final_score,
            converged=converged,
            confidence=final_score,
            summary=f"{len(iterations_out)} refinement iteration(s); timeline updated on disk.",
            max_iterations=max_iter,
            last_quality=last_quality_report,
        )
        record.outputs["refinement"] = refinement_out.model_dump(mode="json", by_alias=True)
        summary_path = get_refinement_summary_json_path(user_id, job_id)
        summary_path.write_text(
            json.dumps(refinement_out.model_dump(mode="json"), ensure_ascii=False),
            encoding="utf-8",
        )

        orch = AgentOrchestrationState(
            phase="multi_agent_complete",
            active_agents=[
                "content_analyzer",
                "story_structure",
                "viral_potential",
                "title_hook",
                "refinement",
            ],
            last_messages=bus.to_ui_dicts(job_id, limit=16),
            refinement_iteration=len(iterations_out) - 1 if iterations_out else None,
            max_refinement_iterations=max_iter,
            refinement_converged=converged,
            final_quality_score=final_score,
        )
        record.outputs["agentOrchestration"] = orch.model_dump(mode="json", by_alias=True)

        now = datetime.now(timezone.utc).isoformat()
        msg_path = get_agent_messages_jsonl_path(user_id, job_id)
        _append_jsonl(
            msg_path,
            {
                "ts": now,
                "type": "pipeline_complete",
                "jobId": job_id,
                "refinementIterations": len(iterations_out),
                "converged": converged,
                "finalQualityScore": final_score,
            },
        )

    def _persist_analysis_and_trace(
        self,
        *,
        user_id: str,
        job_id: str,
        record: JobRecord,
        bus,
        result: AgentResult,
        write_path: Path,
        payload_dump: dict,
        bus_type: str,
        extra_bus: dict,
    ) -> None:
        write_path.write_text(json.dumps(payload_dump, ensure_ascii=False), encoding="utf-8")
        bus.publish_simple(
            job_id=job_id,
            from_agent=result.name,
            type=bus_type,
            payload={"cacheHit": result.cache_hit, "confidence": result.confidence, **extra_bus},
        )
        now = datetime.now(timezone.utc).isoformat()
        _append_trace(
            record,
            AgentTraceEntry(
                agent=result.name,
                ts=now,
                confidence=result.confidence,
                summary=result.summary[:500],
                inputs_hash=result.inputs_hash or None,
                cache_hit=result.cache_hit,
            ),
        )


def run_post_transcript_agents(
    *,
    user_id: str,
    job_id: str,
    transcript: TranscriptResponse,
    record: JobRecord,
) -> None:
    AgentOrchestrator().run_post_transcript_agents(
        user_id=user_id,
        job_id=job_id,
        transcript=transcript,
        record=record,
    )

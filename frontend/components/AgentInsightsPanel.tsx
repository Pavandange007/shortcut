"use client";

import type { FormEvent } from "react";
import { useMemo, useState } from "react";
import type {
  AgentTraceEntry,
  ContentMoment,
  Job,
  ViralClipOutput,
} from "@/lib/types";
import { submitJobFeedback } from "@/lib/api-client";

function formatMs(ms: number): string {
  const s = Math.floor(ms / 1000);
  const m = Math.floor(s / 60);
  const r = s % 60;
  return m > 0 ? `${m}:${r.toString().padStart(2, "0")}` : `${r}s`;
}

function mergeViralWithTitles(job: Job) {
  const clips = job.outputs?.viralAnalysis?.clips ?? [];
  const titles = job.outputs?.titleHookAnalysis?.clips ?? [];
  return clips.map((clip: ViralClipOutput, i: number) => {
    const th =
      titles.find((t) => t.clipIndex === i) ?? titles[i] ?? null;
    return { clip, titleHookSet: th?.titleHookSet };
  });
}

export default function AgentInsightsPanel({
  job,
  onPreviewClipMs,
}: {
  job: Job | undefined;
  onPreviewClipMs?: (startMs: number) => void;
}) {
  const trace = job?.outputs?.agentTrace;
  const orch = job?.outputs?.agentOrchestration;
  const analysis = job?.outputs?.contentAnalysis;
  const story = job?.outputs?.storyAnalysis;
  const refinement = job?.outputs?.refinement;
  const agentErr = job?.outputs?.agentPhaseError;
  const userFb = job?.outputs?.userFeedback;
  const hasSavedFeedback =
    Boolean(userFb) && Object.keys(userFb as object).length > 0;

  const moments = useMemo(() => analysis?.moments ?? [], [analysis]);
  const viralRows = useMemo(() => (job ? mergeViralWithTitles(job) : []), [job]);

  const [fbNotes, setFbNotes] = useState("");
  const [fbAudience, setFbAudience] = useState("");
  const [fbSubmitting, setFbSubmitting] = useState(false);
  const [fbMessage, setFbMessage] = useState<string | null>(null);

  if (!job) return null;

  const hasAgentData =
    Boolean(trace?.length) ||
    Boolean(orch) ||
    Boolean(analysis) ||
    Boolean(story) ||
    Boolean(job.outputs?.viralAnalysis) ||
    Boolean(job.outputs?.titleHookAnalysis) ||
    Boolean(refinement) ||
    Boolean(agentErr) ||
    hasSavedFeedback;

  if (!hasAgentData) return null;

  async function handleFeedbackSubmit(e: FormEvent) {
    e.preventDefault();
    if (!job.id) return;
    setFbSubmitting(true);
    setFbMessage(null);
    try {
      await submitJobFeedback(job.id, {
        notes: fbNotes,
        audience: fbAudience,
      });
      setFbMessage("Saved. Feedback will apply on the next pipeline run that uses agents.");
      setFbNotes("");
      setFbAudience("");
    } catch (err) {
      setFbMessage(err instanceof Error ? err.message : String(err));
    } finally {
      setFbSubmitting(false);
    }
  }

  return (
    <div className="mt-6 space-y-4">
      <div>
        <h2 className="text-sm font-semibold text-foreground/90">
          Agent insights
        </h2>
        <p className="mt-1 text-xs text-foreground/60">
          Multi-agent analysis (content, story, viral, titles) and a bounded refinement loop
          that may adjust your timeline before export.
        </p>
      </div>

      {agentErr ? (
        <div className="rounded-2xl bg-rose-500/10 px-4 py-3 text-xs text-rose-200 ring-1 ring-rose-500/30">
          <span className="font-semibold">Agent phase error</span>
          <pre className="mt-2 max-h-32 overflow-auto whitespace-pre-wrap break-words text-rose-200/90">
            {agentErr}
          </pre>
        </div>
      ) : null}

      {orch ? (
        <div className="rounded-2xl bg-foreground/5 px-4 py-3 text-xs ring-1 ring-foreground/10">
          <div className="font-semibold text-foreground/85">Orchestration</div>
          <div className="mt-2 space-y-1 text-foreground/70">
            <div>
              <span className="text-foreground/50">Phase:</span>{" "}
              {orch.phase || "—"}
            </div>
            {orch.activeAgents?.length ? (
              <div>
                <span className="text-foreground/50">Agents:</span>{" "}
                {orch.activeAgents.join(", ")}
              </div>
            ) : null}
            {orch.maxRefinementIterations != null ? (
              <div>
                <span className="text-foreground/50">Refinement:</span>{" "}
                iter {orch.refinementIteration != null ? orch.refinementIteration + 1 : "—"} /{" "}
                {orch.maxRefinementIterations}
                {orch.refinementConverged != null
                  ? orch.refinementConverged
                    ? " · converged"
                    : " · max iterations"
                  : null}
                {orch.finalQualityScore != null ? (
                  <span className="ml-1 font-mono text-foreground/80">
                    (score {orch.finalQualityScore.toFixed(2)})
                  </span>
                ) : null}
              </div>
            ) : null}
          </div>
          {orch.lastMessages?.length ? (
            <details className="mt-3">
              <summary className="cursor-pointer text-foreground/60">
                Recent bus messages ({orch.lastMessages.length})
              </summary>
              <ul className="mt-2 max-h-40 space-y-2 overflow-auto text-foreground/65">
                {orch.lastMessages.map((m) => (
                  <li key={m.id} className="rounded-lg bg-background/20 px-2 py-1">
                    <span className="text-foreground/45">{m.createdAt}</span>{" "}
                    <span className="font-medium text-foreground/75">
                      {m.fromAgent}
                    </span>
                    <span className="text-foreground/50"> · {m.type}</span>
                  </li>
                ))}
              </ul>
            </details>
          ) : null}
        </div>
      ) : null}

      {refinement ? (
        <div className="rounded-2xl bg-foreground/5 px-4 py-3 text-xs ring-1 ring-foreground/10">
          <div className="font-semibold text-foreground/85">Refinement loop</div>
          {refinement.summary ? (
            <p className="mt-2 text-foreground/65">{refinement.summary}</p>
          ) : null}
          {refinement.iterations?.length ? (
            <ul className="mt-2 max-h-36 space-y-2 overflow-auto text-foreground/70">
              {refinement.iterations.map((it) => (
                <li
                  key={it.iterationIndex}
                  className="rounded-lg bg-background/20 px-2 py-1 font-mono text-[11px]"
                >
                  #{it.iterationIndex + 1}: {it.qualityBefore.toFixed(2)} →{" "}
                  {it.qualityAfter.toFixed(2)}
                  {it.timelineDeltaSummary ? (
                    <div className="mt-1 whitespace-normal font-sans text-foreground/60">
                      {it.timelineDeltaSummary}
                    </div>
                  ) : null}
                </li>
              ))}
            </ul>
          ) : null}
          {refinement.lastQuality ? (
            <div className="mt-3 grid grid-cols-2 gap-2 text-foreground/65 sm:grid-cols-4">
              <div>
                pacing{" "}
                <span className="font-mono text-foreground/85">
                  {refinement.lastQuality.pacing?.toFixed(2) ?? "—"}
                </span>
              </div>
              <div>
                clarity{" "}
                <span className="font-mono text-foreground/85">
                  {refinement.lastQuality.clarity?.toFixed(2) ?? "—"}
                </span>
              </div>
              <div>
                hooks{" "}
                <span className="font-mono text-foreground/85">
                  {refinement.lastQuality.hookStrength?.toFixed(2) ?? "—"}
                </span>
              </div>
              <div>
                redundancy{" "}
                <span className="font-mono text-foreground/85">
                  {refinement.lastQuality.redundancy?.toFixed(2) ?? "—"}
                </span>
              </div>
            </div>
          ) : null}
        </div>
      ) : null}

      {analysis ? (
        <div className="rounded-2xl bg-foreground/5 px-4 py-3 text-xs ring-1 ring-foreground/10">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <div className="font-semibold text-foreground/85">
              Content analysis
            </div>
            <div className="text-foreground/55">
              confidence{" "}
              <span className="font-mono text-foreground/80">
                {typeof analysis.confidence === "number"
                  ? analysis.confidence.toFixed(2)
                  : "—"}
              </span>
            </div>
          </div>
          {analysis.summary ? (
            <p className="mt-2 text-foreground/70">{analysis.summary}</p>
          ) : null}
          {moments.length ? (
            <ul className="mt-3 max-h-48 space-y-2 overflow-auto">
              {moments.map((mo: ContentMoment, i: number) => (
                <li
                  key={`${mo.startMs}-${mo.endMs}-${i}`}
                  className="rounded-xl bg-background/25 px-3 py-2 ring-1 ring-foreground/10"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="font-medium text-foreground/85">
                      {mo.label || "Moment"}
                    </span>
                    <span className="font-mono text-foreground/55">
                      {formatMs(mo.startMs)}–{formatMs(mo.endMs)}
                    </span>
                  </div>
                  <div className="mt-1 text-foreground/50">
                    impact{" "}
                    <span className="font-mono text-foreground/75">
                      {typeof mo.impactScore === "number"
                        ? mo.impactScore.toFixed(2)
                        : "—"}
                    </span>
                  </div>
                  {mo.evidence ? (
                    <p className="mt-1 text-foreground/65">&ldquo;{mo.evidence}&rdquo;</p>
                  ) : null}
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-2 text-foreground/55">No moments returned.</p>
          )}
        </div>
      ) : null}

      {story?.beats?.length ? (
        <div className="rounded-2xl bg-foreground/5 px-4 py-3 text-xs ring-1 ring-foreground/10">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <div className="font-semibold text-foreground/85">Story structure</div>
            <span className="text-foreground/55">
              conf.{" "}
              <span className="font-mono">
                {typeof story.confidence === "number"
                  ? story.confidence.toFixed(2)
                  : "—"}
              </span>
            </span>
          </div>
          {story.narrativeSummary ? (
            <p className="mt-2 text-foreground/70">{story.narrativeSummary}</p>
          ) : null}
          <ul className="mt-2 max-h-40 space-y-2 overflow-auto">
            {story.beats.map((b, i) => (
              <li
                key={`${b.startMs}-${b.endMs}-${i}`}
                className="rounded-lg bg-background/20 px-2 py-1.5"
              >
                <span className="rounded bg-violet-500/20 px-1.5 py-0.5 text-violet-200">
                  {b.role ?? "other"}
                </span>
                <span className="ml-2 font-mono text-foreground/55">
                  {formatMs(b.startMs)}–{formatMs(b.endMs)}
                </span>
                {b.summary ? (
                  <div className="mt-1 text-foreground/65">{b.summary}</div>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {viralRows.length ? (
        <div className="rounded-2xl bg-foreground/5 px-4 py-3 text-xs ring-1 ring-foreground/10">
          <div className="font-semibold text-foreground/85">
            Viral clips & titles
          </div>
          <p className="mt-1 text-foreground/55">
            Preview jumps the rough cut to each clip start (after export).
          </p>
          <ul className="mt-3 max-h-64 space-y-3 overflow-auto">
            {viralRows.map(({ clip, titleHookSet }, i) => (
              <li
                key={`${clip.startMs}-${clip.endMs}-${i}`}
                className="rounded-xl bg-background/25 px-3 py-2 ring-1 ring-foreground/10"
              >
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <div className="font-medium text-foreground/85">
                      {titleHookSet?.primaryTitle || `Clip ${i + 1}`}
                    </div>
                    <div className="mt-1 font-mono text-foreground/55">
                      {formatMs(clip.startMs)}–{formatMs(clip.endMs)} · viral{" "}
                      {typeof clip.viralScore === "number"
                        ? clip.viralScore.toFixed(2)
                        : "—"}
                    </div>
                    {clip.rationale ? (
                      <p className="mt-1 text-foreground/65">{clip.rationale}</p>
                    ) : null}
                    {titleHookSet?.hooks?.length ? (
                      <ul className="mt-2 list-inside list-disc text-foreground/60">
                        {titleHookSet.hooks.slice(0, 4).map((h, j) => (
                          <li key={j}>{h}</li>
                        ))}
                      </ul>
                    ) : null}
                    {clip.platformRecommendations?.length ? (
                      <div className="mt-2 text-foreground/50">
                        platforms: {clip.platformRecommendations.join(", ")}
                      </div>
                    ) : null}
                  </div>
                  {onPreviewClipMs ? (
                    <button
                      type="button"
                      className="shrink-0 rounded-full bg-foreground/15 px-3 py-1 text-[11px] font-medium text-foreground/85 ring-1 ring-foreground/15 hover:bg-foreground/25"
                      onClick={() => onPreviewClipMs(clip.startMs)}
                    >
                      Preview
                    </button>
                  ) : null}
                </div>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {hasSavedFeedback ? (
        <div className="rounded-2xl bg-foreground/5 px-4 py-3 text-xs text-foreground/70 ring-1 ring-foreground/10">
          <div className="font-semibold text-foreground/85">Saved feedback</div>
          <pre className="mt-2 max-h-24 overflow-auto whitespace-pre-wrap break-words">
            {JSON.stringify(userFb, null, 2)}
          </pre>
        </div>
      ) : null}

      <form
        onSubmit={handleFeedbackSubmit}
        className="rounded-2xl bg-foreground/5 px-4 py-3 text-xs ring-1 ring-foreground/10"
      >
        <div className="font-semibold text-foreground/85">Agent feedback</div>
        <p className="mt-1 text-foreground/55">
          Notes are stored on the job and read by refinement when you upload a new run or when
          we add re-refinement.
        </p>
        <label className="mt-2 block">
          <span className="text-foreground/50">Notes</span>
          <textarea
            className="mt-1 w-full rounded-xl border border-foreground/15 bg-background/30 px-3 py-2 text-sm text-foreground"
            rows={3}
            value={fbNotes}
            onChange={(e) => setFbNotes(e.target.value)}
            placeholder="Tone, must-keep lines, platform…"
          />
        </label>
        <label className="mt-2 block">
          <span className="text-foreground/50">Audience</span>
          <input
            className="mt-1 w-full rounded-xl border border-foreground/15 bg-background/30 px-3 py-2 text-sm text-foreground"
            value={fbAudience}
            onChange={(e) => setFbAudience(e.target.value)}
            placeholder="e.g. beginner developers"
          />
        </label>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <button
            type="submit"
            disabled={fbSubmitting}
            className="rounded-full bg-foreground/20 px-4 py-1.5 text-xs font-medium text-foreground/90 ring-1 ring-foreground/20 hover:bg-foreground/30 disabled:opacity-50"
          >
            {fbSubmitting ? "Saving…" : "Save feedback"}
          </button>
          {fbMessage ? (
            <span className="text-foreground/60">{fbMessage}</span>
          ) : null}
        </div>
      </form>

      {trace?.length ? (
        <div className="rounded-2xl bg-foreground/5 px-4 py-3 text-xs ring-1 ring-foreground/10">
          <div className="font-semibold text-foreground/85">Agent trace</div>
          <ul className="mt-2 space-y-2">
            {trace.map((t: AgentTraceEntry, i: number) => (
              <li key={`${t.ts}-${t.agent}-${i}`} className="text-foreground/70">
                <span className="text-foreground/45">{t.ts}</span>{" "}
                <span className="font-medium text-foreground/85">{t.agent}</span>
                {t.cacheHit ? (
                  <span className="ml-2 rounded-full bg-emerald-500/15 px-2 py-0.5 text-[10px] text-emerald-200 ring-1 ring-emerald-500/25">
                    cache
                  </span>
                ) : null}
                {typeof t.confidence === "number" ? (
                  <span className="ml-2 font-mono text-foreground/55">
                    {t.confidence.toFixed(2)}
                  </span>
                ) : null}
                {t.summary ? (
                  <div className="mt-1 text-foreground/60">{t.summary}</div>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

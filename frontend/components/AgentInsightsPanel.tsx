"use client";

import type { FormEvent } from "react";
import { useEffect, useMemo, useState } from "react";
import type {
  AgentTraceEntry,
  ContentMoment,
  Job,
  ViralClipOutput,
} from "@/lib/types";
import { submitJobChatMessage } from "@/lib/api-client";
import type { JobChatMessage } from "@/lib/types";

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
  onPreviewClipRange,
}: {
  job: Job | undefined;
  onPreviewClipRange?: (startMs: number, endMs: number) => void;
}) {
  const trace = job?.outputs?.agentTrace;
  const orch = job?.outputs?.agentOrchestration;
  const analysis = job?.outputs?.contentAnalysis;
  const story = job?.outputs?.storyAnalysis;
  const refinement = job?.outputs?.refinement;
  const agentErr = job?.outputs?.agentPhaseError;

  const moments = useMemo(() => analysis?.moments ?? [], [analysis]);
  const viralRows = useMemo(() => (job ? mergeViralWithTitles(job) : []), [job]);

  const [chatInput, setChatInput] = useState("");
  const [chatSubmitting, setChatSubmitting] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);
  const [optimisticChat, setOptimisticChat] = useState<JobChatMessage[]>([]);
  const [activeTab, setActiveTab] = useState<"overview" | "clips" | "story" | "chat">("overview");
  const [highlightClip, setHighlightClip] = useState<number | null>(null);

  const persistedChat = useMemo(
    () => (job?.outputs?.chatHistory ?? []) as JobChatMessage[],
    [job?.outputs?.chatHistory],
  );

  const chatMessages = useMemo(() => {
    const byId = new Map<string, JobChatMessage>();
    for (const m of persistedChat) byId.set(m.id, m);
    for (const m of optimisticChat) if (!byId.has(m.id)) byId.set(m.id, m);
    return Array.from(byId.values()).sort((a, b) =>
      a.createdAt.localeCompare(b.createdAt),
    );
  }, [optimisticChat, persistedChat]);

  useEffect(() => {
    if (!persistedChat.length) return;
    setOptimisticChat((prev) =>
      prev.filter((m) => !persistedChat.some((p) => p.id === m.id)),
    );
  }, [persistedChat]);

  async function handleChatSubmit(e: FormEvent) {
    e.preventDefault();
    if (!job?.id) return;
    const message = chatInput.trim();
    if (!message) return;

    setChatSubmitting(true);
    setChatError(null);
    try {
      const res = await submitJobChatMessage(job.id, { message });
      const nowIso = new Date().toISOString();
      setOptimisticChat((prev) => [
        ...prev,
        {
          id: res.userMessageId,
          role: "user",
          text: message,
          createdAt: nowIso,
          status: "done",
        },
        {
          id: res.assistantMessageId,
          role: "assistant",
          text: "Working…",
          createdAt: nowIso,
          status: "queued",
        },
      ]);
      setChatInput("");
    } catch (err) {
      setChatError(err instanceof Error ? err.message : String(err));
    } finally {
      setChatSubmitting(false);
    }
  }

  const hasAgentData =
    Boolean(job) &&
    (Boolean(trace?.length) ||
    Boolean(orch) ||
    Boolean(analysis) ||
    Boolean(story) ||
    Boolean(job?.outputs?.viralAnalysis) ||
    Boolean(job?.outputs?.titleHookAnalysis) ||
    Boolean(refinement) ||
    Boolean(agentErr) ||
    Boolean(persistedChat.length) ||
    Boolean(optimisticChat.length));

  if (!hasAgentData) return null;

  const tabs: Array<{ id: "overview" | "clips" | "story" | "chat"; label: string }> = [
    { id: "overview", label: "Overview" },
    { id: "clips", label: "Clips" },
    { id: "story", label: "Story" },
    { id: "chat", label: "Chat" },
  ];

  return (
    <div className="mt-6 space-y-4 animate-fade-in">
      <div>
        <h2 className="text-sm font-semibold text-foreground/90">
          AI co-pilot insights
        </h2>
        <p className="mt-1 text-xs text-foreground/60">
          Multi-agent analysis (content, story, viral, titles) and a bounded refinement loop
          that may adjust your timeline before export.
        </p>
      </div>

      <div className="flex flex-wrap gap-2">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => setActiveTab(tab.id)}
            className={[
              "rounded-full px-3 py-1.5 text-xs transition",
              activeTab === tab.id
                ? "bg-gradient-to-r from-accent to-accent-2 text-white"
                : "bg-surface-2/80 text-muted-foreground hover:text-foreground",
            ].join(" ")}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {agentErr ? (
        <div className="rounded-2xl bg-rose-500/10 px-4 py-3 text-xs text-rose-200 ring-1 ring-rose-500/30">
          <span className="font-semibold">Agent phase error</span>
          <pre className="mt-2 max-h-32 overflow-auto whitespace-pre-wrap break-words text-rose-200/90">
            {agentErr}
          </pre>
        </div>
      ) : null}

      {activeTab === "overview" && orch ? (
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

      {activeTab === "overview" && refinement ? (
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

      {activeTab === "overview" && analysis ? (
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

      {activeTab === "story" && story?.beats?.length ? (
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

      {activeTab === "clips" && viralRows.length ? (
        <div className="rounded-2xl bg-foreground/5 px-4 py-3 text-xs ring-1 ring-foreground/10 animate-slide-up">
          <div className="font-semibold text-foreground/85">
            Viral clips & titles
          </div>
          <p className="mt-1 text-foreground/55">
            Preview exports a clip for the timestamps returned by Gemini.
          </p>
          <ul className="mt-3 grid max-h-[28rem] grid-cols-1 gap-3 overflow-auto md:grid-cols-2">
            {viralRows.map(({ clip, titleHookSet }, i) => (
              <li
                key={`${clip.startMs}-${clip.endMs}-${i}`}
                className={[
                  "rounded-xl bg-background/25 px-3 py-3 ring-1 ring-foreground/10 transition",
                  highlightClip === i ? "ring-accent/70" : "",
                ].join(" ")}
              >
                <div className="mb-2 h-24 rounded-lg bg-surface-2/80" />
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
                    <div className="mt-2">
                      <div className="mb-1 text-[11px] text-muted-foreground">Virality score</div>
                      <div className="h-1.5 rounded-full bg-surface-3">
                        <div
                          className="h-full rounded-full bg-gradient-to-r from-accent to-accent-2"
                          style={{
                            width: `${Math.max(8, Math.min(100, (clip.viralScore ?? 0.2) * 100))}%`,
                          }}
                        />
                      </div>
                    </div>
                    {clip.platformRecommendations?.length ? (
                      <div className="mt-2 text-foreground/50">
                        platforms: {clip.platformRecommendations.join(", ")}
                      </div>
                    ) : null}
                  </div>
                  {onPreviewClipRange ? (
                    <div className="flex shrink-0 gap-2">
                      <button
                        type="button"
                        className="rounded-full bg-foreground/15 px-3 py-1 text-[11px] font-medium text-foreground/85 ring-1 ring-foreground/15 hover:bg-foreground/25"
                        onClick={() => {
                          setHighlightClip(i);
                          onPreviewClipRange(clip.startMs, clip.endMs);
                        }}
                      >
                        Preview
                      </button>
                      <button
                        type="button"
                        className="rounded-full bg-accent/20 px-3 py-1 text-[11px] font-medium text-accent-2 ring-1 ring-accent/35 hover:bg-accent/30"
                      >
                        Add to Timeline
                      </button>
                    </div>
                  ) : null}
                </div>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {activeTab === "chat" ? (
      <form
        onSubmit={handleChatSubmit}
        className="rounded-2xl bg-foreground/5 px-4 py-3 text-xs ring-1 ring-foreground/10 animate-slide-up"
      >
        <div className="font-semibold text-foreground/85">Agent chat</div>
        <p className="mt-1 text-foreground/55">
          Ask for clip candidates, hooks, or refinements. Example: “give me 6 viral clips around 20
          seconds each”.
        </p>

        {chatMessages.length ? (
          <ul className="mt-3 max-h-56 space-y-2 overflow-auto">
            {chatMessages.map((m) => (
              <li
                key={m.id}
                className={
                  m.role === "user"
                    ? "ml-auto max-w-[85%] rounded-xl bg-background/25 px-3 py-2 text-foreground/80 ring-1 ring-foreground/10"
                    : "max-w-[85%] rounded-xl bg-violet-500/10 px-3 py-2 text-foreground/80 ring-1 ring-violet-500/20"
                }
              >
                <div className="flex items-baseline justify-between gap-2">
                  <span className="text-[10px] uppercase tracking-wide text-foreground/45">
                    {m.role}
                    {m.status && m.status !== "done" ? ` · ${m.status}` : ""}
                  </span>
                  <span className="text-[10px] text-foreground/40">{m.createdAt}</span>
                </div>
                <div className="mt-1 whitespace-pre-wrap text-xs text-foreground/75">
                  {m.text}
                </div>
                {m.error ? (
                  <div className="mt-1 text-xs text-rose-200/90">{m.error}</div>
                ) : null}
              </li>
            ))}
          </ul>
        ) : null}

        {chatMessages.some((m) => m.role === "assistant" && m.status !== "done") ? (
          <div className="mt-2 inline-flex items-center gap-1 text-xs text-muted-foreground">
            <span className="animate-pulse">.</span>
            <span className="animate-pulse [animation-delay:120ms]">.</span>
            <span className="animate-pulse [animation-delay:240ms]">.</span>
            AI is thinking
          </div>
        ) : null}

        <label className="mt-3 block">
          <span className="text-foreground/50">Message</span>
          <textarea
            className="mt-1 w-full resize-y rounded-xl border border-foreground/15 bg-background/30 px-3 py-2 text-sm text-foreground"
            rows={2}
            value={chatInput}
            onChange={(e) => setChatInput(e.target.value)}
            placeholder="e.g. give me 20 second viral clips from this video"
          />
        </label>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <button
            type="submit"
            disabled={chatSubmitting}
            className="rounded-full bg-foreground/20 px-4 py-1.5 text-xs font-medium text-foreground/90 ring-1 ring-foreground/20 hover:bg-foreground/30 disabled:opacity-50"
          >
            {chatSubmitting ? "Sending…" : "Send"}
          </button>
          {chatError ? <span className="text-rose-200/90">{chatError}</span> : null}
        </div>
      </form>
      ) : null}

      {activeTab === "overview" && trace?.length ? (
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

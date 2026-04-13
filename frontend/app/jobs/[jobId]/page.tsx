"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import AgentInsightsPanel from "@/components/AgentInsightsPanel";
import JobProgress from "@/components/JobProgress";
import VideoPreview from "@/components/VideoPreview";
import Button from "@/components/Button";
import SkeletonLoader from "@/components/SkeletonLoader";
import type { JobStepKey, StepState } from "@/lib/types";
import {
  getApiBaseUrl,
  getJobStatus,
  isJobForbiddenError,
  isJobNotFoundError,
  serializeUnknownError,
} from "@/lib/api-client";
import type { Job } from "@/lib/types";

const stepKeys: JobStepKey[] = [
  "silence_removal",
  "best_take",
  "captions",
  "export",
];

function computeStepStates(job?: Job): Record<JobStepKey, StepState> {
  const base: Record<JobStepKey, StepState> = {
    silence_removal: "pending",
    best_take: "pending",
    captions: "pending",
    export: "pending",
  };

  if (!job) return base;
  for (const key of stepKeys) base[key] = job.steps[key] ?? "pending";
  return base;
}

export default function JobDetailsPage() {
  const pathname = usePathname();
  const router = useRouter();
  const jobId = useMemo(() => {
    const segments = pathname.split("/").filter(Boolean);
    return segments[1] ?? "";
  }, [pathname]);
  const [showError, setShowError] = useState(false);
  const [previewSeekMs, setPreviewSeekMs] = useState<number | null>(null);
  const [previewClipUrl, setPreviewClipUrl] = useState<string | null>(null);
  const [leftPanelPct, setLeftPanelPct] = useState(38);
  const [isInsightsCollapsed, setIsInsightsCollapsed] = useState(false);

  const handleSeekConsumed = useCallback(() => {
    setPreviewSeekMs(null);
  }, []);

  const handlePreviewClipRange = useCallback(
    (startMs: number, endMs: number) => {
      if (!jobId) return;
      setPreviewClipUrl(
        `/jobs/${encodeURIComponent(jobId)}/clip?startMs=${encodeURIComponent(String(startMs))}&endMs=${encodeURIComponent(String(endMs))}`,
      );
      setPreviewSeekMs(0);
    },
    [jobId],
  );

  const jobQuery = useQuery<Job, Error>({
    queryKey: ["jobStatus", jobId],
    enabled: Boolean(jobId),
    queryFn: () => getJobStatus(jobId),
    refetchInterval: (query) => {
      if (query.state.status === "error") return false;
      const j = query.state.data;
      if (!j) return 2000;
      if (j.overallStatus === "completed" || j.overallStatus === "failed") return false;
      return 2000;
    },
    retry: 0,
  });

  const job = jobQuery.data;
  const stepStates = useMemo(() => computeStepStates(job), [job]);
  const lastJobJson = useRef<string>("");
  const lastPollErrorKey = useRef<string>("");
  const dragRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!jobId) return;
    if (jobQuery.isError && jobQuery.error) {
      const parts = serializeUnknownError(jobQuery.error);
      const key = `${parts.errorMessage}\n${parts.errorStack ?? ""}`;
      if (key !== lastPollErrorKey.current) {
        lastPollErrorKey.current = key;
        console.error("[Shortcut] job poll failed", {
          jobId,
          apiUrl: `${getApiBaseUrl()}/jobs/${jobId}`,
          ...parts,
        });
        console.error("[Shortcut] job poll failed (raw)", jobQuery.error);
      }
      return;
    }
    lastPollErrorKey.current = "";
    if (!job) return;
    const serialized = JSON.stringify(job);
    if (serialized === lastJobJson.current) return;
    lastJobJson.current = serialized;
    const hasIssue = Boolean(
      job.outputs?.error ||
        job.outputs?.error_export ||
        job.outputs?.error_caption_burn,
    );
    if (hasIssue) {
      console.warn("[Shortcut] job update (issues)", jobId, job);
    } else {
      console.log("[Shortcut] job update", jobId, {
        overallStatus: job.overallStatus,
        steps: job.steps,
        outputs: job.outputs,
      });
    }
  }, [jobId, job, jobQuery.isError, jobQuery.error]);

  useEffect(() => {
    function onMove(e: MouseEvent) {
      if (!dragRef.current) return;
      const rect = dragRef.current.getBoundingClientRect();
      const pct = ((e.clientX - rect.left) / rect.width) * 100;
      setLeftPanelPct(Math.min(62, Math.max(26, pct)));
    }
    function onUp() {
      document.body.style.cursor = "";
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    }
    const divider = dragRef.current?.querySelector("[data-divider='true']");
    if (!divider) return;
    const onDown = () => {
      document.body.style.cursor = "col-resize";
      window.addEventListener("mousemove", onMove);
      window.addEventListener("mouseup", onUp);
    };
    divider.addEventListener("mousedown", onDown);
    return () => {
      divider.removeEventListener("mousedown", onDown);
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
      document.body.style.cursor = "";
    };
  }, []);

  const clipMarkers =
    job?.outputs?.viralAnalysis?.clips?.map((clip, i) => ({
      startMs: clip.startMs,
      endMs: clip.endMs,
      label: `Clip ${i + 1}`,
    })) ?? [];

  return (
    <main className="mx-auto w-full max-w-[1440px] flex-1 px-6 py-8">
      <div className="mb-5 panel-surface rounded-3xl p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <h1 className="truncate text-2xl font-semibold">Job {jobId}</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Collaborate with AI agents while your rough cut is analyzed, refined, and exported.
            </p>
          </div>
          <div className="flex gap-2">
            <Button variant="ghost" onClick={() => setIsInsightsCollapsed((v) => !v)}>
              {isInsightsCollapsed ? "Show Insights" : "Hide Insights"}
            </Button>
            <Button variant="secondary" onClick={() => router.push("/upload")}>
              Back
            </Button>
          </div>
        </div>
        <div className="mt-5">
          <JobProgress statusByStep={stepStates} />
        </div>
      </div>

      <div ref={dragRef} className="flex min-h-[520px] gap-0">
        {!isInsightsCollapsed ? (
          <section className="pr-3" style={{ width: `${leftPanelPct}%` }}>
            <div className="panel-surface h-full rounded-3xl p-6">
              {jobQuery.isPending ? (
                <div className="space-y-3">
                  <SkeletonLoader className="h-5 w-1/2" />
                  <SkeletonLoader className="h-24 w-full" />
                  <SkeletonLoader className="h-24 w-full" />
                </div>
              ) : null}

              <AgentInsightsPanel job={job} onPreviewClipRange={handlePreviewClipRange} />

              {stepStates.silence_removal === "running" ? (
                <p className="mt-4 rounded-2xl bg-warning/10 px-4 py-3 text-xs text-warning ring-1 ring-warning/25">
                  <span className="font-semibold">Transcription in progress.</span> First run may
                  download Whisper weights and can take several minutes.
                </p>
              ) : null}
            </div>
          </section>
        ) : null}

        {!isInsightsCollapsed ? (
          <div
            data-divider="true"
            className="mt-2 hidden w-2 cursor-col-resize rounded-full bg-white/10 hover:bg-accent/60 lg:block"
          />
        ) : null}

        <section className={isInsightsCollapsed ? "w-full" : "pl-3"} style={isInsightsCollapsed ? undefined : { width: `${100 - leftPanelPct}%` }}>
          <div className="panel-surface h-full rounded-3xl p-6">
            {job?.outputs?.error ? (
              <div className="mb-4 rounded-2xl bg-rose-500/10 px-4 py-3 text-sm text-rose-200 ring-1 ring-rose-500/30">
                <div className="font-semibold">Pipeline error</div>
                <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap break-words text-xs text-rose-200/90">
                  {job.outputs.error}
                </pre>
              </div>
            ) : null}

            {job?.outputs?.error_export ? (
              <div className="mt-4 rounded-2xl bg-amber-500/10 px-4 py-3 text-sm text-amber-100 ring-1 ring-amber-500/30">
                <div className="font-semibold">Export notice</div>
                <p className="mt-1 text-xs text-amber-100/90">
                  Transcript and captions may still be available. Rough-cut export failed:
                </p>
                <pre className="mt-2 max-h-32 overflow-auto whitespace-pre-wrap break-words text-xs">
                  {job.outputs.error_export}
                </pre>
              </div>
            ) : null}

            {job?.outputs?.error_caption_burn ? (
              <div className="mt-4 rounded-2xl bg-amber-500/10 px-4 py-3 text-sm text-amber-100 ring-1 ring-amber-500/30">
                <div className="font-semibold">Caption burn-in notice</div>
                <p className="mt-1 text-xs text-amber-100/90">
                  Rough cut exported without burned-in subtitles (FFmpeg or subtitle step failed). The
                  preview is the silence-stripped cut only.
                </p>
                <pre className="mt-2 max-h-32 overflow-auto whitespace-pre-wrap break-words text-xs">
                  {job.outputs.error_caption_burn}
                </pre>
              </div>
            ) : null}

            {jobQuery.isError ? (
              <div className="mb-4 rounded-2xl bg-rose-500/10 px-4 py-3 text-sm text-rose-200 ring-1 ring-rose-500/30">
                <div className="font-semibold">
                  {jobQuery.error && isJobNotFoundError(jobQuery.error)
                    ? "Job not found on the server"
                    : "Could not fetch job status."}
                </div>
                <div className="mt-1 text-rose-200/90">
                  {jobQuery.error && isJobNotFoundError(jobQuery.error)
                    ? "Jobs are stored in memory on the API. After a backend restart, old links and “Recent jobs” IDs are invalid — start a new upload."
                    : jobQuery.error && isJobForbiddenError(jobQuery.error)
                      ? "Your session changed. This job belongs to a different session token — start a new upload."
                      : "Ensure the FastAPI backend is running at the URL in NEXT_PUBLIC_API_BASE_URL (default http://localhost:8000)."}
                </div>
                {showError ? (
                  <pre className="mt-3 whitespace-pre-wrap text-xs">
                    {jobQuery.error instanceof Error ? jobQuery.error.message : String(jobQuery.error)}
                  </pre>
                ) : null}
                <div className="mt-2">
                  <Button variant="ghost" onClick={() => setShowError((v) => !v)}>
                    {showError ? "Hide details" : "Show details"}
                  </Button>
                </div>
              </div>
            ) : null}
            <VideoPreview
              roughCutUrl={previewClipUrl ?? job?.outputs?.roughCutUrl}
              mediaRevision={job?.outputs?.media_revision}
              title="Rough cut preview"
              seekToMs={previewSeekMs}
              onSeekConsumed={handleSeekConsumed}
              markers={clipMarkers}
              onMarkerClick={(idx) => {
                const m = clipMarkers[idx];
                if (!m) return;
                handlePreviewClipRange(m.startMs, m.endMs);
              }}
            />

            {previewClipUrl ? (
              <div className="mt-3 flex items-center justify-between gap-3">
                <div className="text-xs text-foreground/60">Showing a Gemini clip preview.</div>
                <Button
                  variant="ghost"
                  onClick={() => {
                    setPreviewClipUrl(null);
                    setPreviewSeekMs(null);
                  }}
                >
                  Back to rough cut
                </Button>
              </div>
            ) : null}

            <div className="mt-5 text-sm text-foreground/70">
              {job?.overallStatus === "failed"
                ? "Job failed — see the error above."
                : job?.overallStatus === "completed" && job?.outputs?.roughCutUrl
                  ? job?.outputs?.error_caption_burn
                    ? "Rough cut is ready (subtitles could not be burned in — see notice above)."
                    : "Rough cut with burned-in captions is ready to preview."
                  : job?.overallStatus === "completed" && job?.outputs?.error_export
                    ? "Pipeline finished without a rough cut (usually FFmpeg missing on the server)."
                    : job?.overallStatus === "completed"
                      ? "Completed — if there is no video, check export logs or FFmpeg installation."
                      : jobQuery.isPending
                        ? "Waiting for transcription & timeline generation..."
                        : "Generating your edit..."}
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}


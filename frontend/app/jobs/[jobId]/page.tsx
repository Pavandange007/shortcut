"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import JobProgress from "@/components/JobProgress";
import VideoPreview from "@/components/VideoPreview";
import Button from "@/components/Button";
import type { JobStepKey, StepState } from "@/lib/types";
import {
  getApiBaseUrl,
  getJobStatus,
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
  const params = useParams<{ jobId: string }>();
  const router = useRouter();
  const jobId = params.jobId;
  const [showError, setShowError] = useState(false);

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

  return (
    <main className="mx-auto w-full max-w-6xl flex-1 px-6 py-10">
      <div className="flex flex-col gap-6 lg:flex-row lg:items-start">
        <section className="w-full lg:w-5/12">
          <div className="rounded-3xl bg-background/10 p-6 ring-1 ring-foreground/10">
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0">
                <h1 className="truncate text-lg font-semibold">
                  Job {jobId}
                </h1>
                <p className="mt-2 text-sm text-foreground/70">
                  Track the pipeline: silence removal, best take selection,
                  captions, and rough-cut export.
                </p>
              </div>
              <Button
                variant="ghost"
                onClick={() => router.push("/upload")}
              >
                Back
              </Button>
            </div>

            <div className="mt-6">
              <JobProgress statusByStep={stepStates} />
            </div>

            {stepStates.silence_removal === "running" ? (
              <p className="mt-4 rounded-2xl bg-amber-500/10 px-4 py-3 text-xs text-amber-100/95 ring-1 ring-amber-500/25">
                <span className="font-semibold text-amber-100">Transcription in progress.</span> The
                first run downloads the Whisper model (can be 1GB+) and CPU transcription is slow
                (often many minutes for longer clips). Watch the API terminal for{" "}
                <code className="rounded bg-foreground/10 px-1">whisper:</code> log lines. For faster
                dev, set <code className="rounded bg-foreground/10 px-1">WHISPER_MODEL_NAME=base</code>{" "}
                or <code className="rounded bg-foreground/10 px-1">tiny</code> in backend{" "}
                <code className="rounded bg-foreground/10 px-1">.env</code>.
              </p>
            ) : null}

            {job?.outputs?.error ? (
              <div className="mt-5 rounded-2xl bg-rose-500/10 px-4 py-3 text-sm text-rose-200 ring-1 ring-rose-500/30">
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
              <div className="mt-5 rounded-2xl bg-rose-500/10 px-4 py-3 text-sm text-rose-200 ring-1 ring-rose-500/30">
                <div className="font-semibold">
                  {jobQuery.error && isJobNotFoundError(jobQuery.error)
                    ? "Job not found on the server"
                    : "Could not fetch job status."}
                </div>
                <div className="mt-1 text-rose-200/90">
                  {jobQuery.error && isJobNotFoundError(jobQuery.error)
                    ? "Jobs are stored in memory on the API. After a backend restart, old links and “Recent jobs” IDs are invalid — start a new upload."
                    : "Ensure the FastAPI backend is running at the URL in NEXT_PUBLIC_API_BASE_URL (default http://localhost:8000)."}
                </div>
                {showError ? (
                  <pre className="mt-3 whitespace-pre-wrap text-xs">
                    {jobQuery.error instanceof Error ? jobQuery.error.message : String(jobQuery.error)}
                  </pre>
                ) : null}
                <div className="mt-2">
                  <Button
                    variant="ghost"
                    onClick={() => setShowError((v) => !v)}
                  >
                    {showError ? "Hide details" : "Show details"}
                  </Button>
                </div>
              </div>
            ) : null}
          </div>
        </section>

        <section className="w-full lg:w-7/12">
          <div className="rounded-3xl bg-background/10 p-6 ring-1 ring-foreground/10">
            <VideoPreview
              roughCutUrl={job?.outputs?.roughCutUrl}
              mediaRevision={job?.outputs?.media_revision}
              title="Rough cut preview"
            />

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


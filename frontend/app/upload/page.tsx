"use client";

import { useMemo, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import UploadDropzone from "@/components/UploadDropzone";
import type { JobOverallStatus } from "@/lib/types";
import { createJob, uploadVideo } from "@/lib/api-client";

type RecentJob = {
  jobId: string;
  createdAt: number;
  status: JobOverallStatus;
};

const RECENTS_KEY = "shotcut_ai_recents_v1";

function loadRecents(): RecentJob[] {
  try {
    const raw = localStorage.getItem(RECENTS_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as RecentJob[];
    if (!Array.isArray(parsed)) return [];
    return parsed.slice(0, 8);
  } catch {
    return [];
  }
}

function saveRecents(jobs: RecentJob[]) {
  localStorage.setItem(RECENTS_KEY, JSON.stringify(jobs.slice(0, 8)));
}

export default function UploadPage() {
  const router = useRouter();
  // Empty on first paint so SSR and hydration match; localStorage read only after mount.
  // We use the second state initializer arg to avoid setState-in-effect lint.
  const [recents, setRecents] = useState<RecentJob[]>(
    [],
    () => loadRecents(),
  );
  const [pageError, setPageError] = useState<string | null>(null);

  const recentJobsLabel = useMemo(() => {
    if (recents.length === 0) return "No recent jobs yet";
    return "Recent jobs";
  }, [recents.length]);

  const createAndUploadMutation = useMutation({
    mutationFn: async (file: File) => {
      setPageError(null);
      const { jobId } = await createJob();
      await uploadVideo(jobId, file);
      return jobId;
    },
  });

  async function handleUpload(file: File) {
    try {
      setPageError(null);
      const jobId = await createAndUploadMutation.mutateAsync(file);
      const next: RecentJob = {
        jobId,
        createdAt: Date.now(),
        status: "queued",
      };
      const merged = [next, ...recents.filter((r) => r.jobId !== jobId)].slice(
        0,
        8,
      );
      setRecents(merged);
      saveRecents(merged);
      router.push(`/jobs/${jobId}`);
    } catch (e) {
      setPageError(e instanceof Error ? e.message : "Upload failed.");
    }
  }

  return (
    <main className="mx-auto w-full max-w-6xl flex-1 px-6 py-10">
      <div className="grid grid-cols-1 gap-8 lg:grid-cols-3">
        <section className="rounded-3xl bg-background/10 p-6 ring-1 ring-foreground/10 lg:col-span-1">
          <h1 className="text-xl font-semibold tracking-tight">
            AI Video Editor MVP
          </h1>
          <p className="mt-2 text-sm text-foreground/70">
            Upload a video, then we generate a rough cut by analyzing pacing,
            removing silent gaps, and burning millisecond-accurate captions.
          </p>

          <div className="mt-6 flex flex-col gap-3">
            {[
              ["silence_removal", "1. Silence Removal"],
              ["best_take", "2. Best Take"],
              ["captions", "3. Captions"],
              ["export", "4. Export Rough Cut"],
            ].map(([key, label], idx) => (
              <div
                key={key}
                className={[
                  "flex items-center justify-between rounded-2xl px-4 py-3 ring-1 ring-foreground/10",
                  idx === 0 ? "bg-foreground/5" : "bg-background/10",
                ].join(" ")}
              >
                <span className="text-sm font-semibold">{label}</span>
                <span className="text-xs text-foreground/60">Pluggable</span>
              </div>
            ))}
          </div>
        </section>

        <section className="lg:col-span-1">
          <UploadDropzone
            onUpload={handleUpload}
            isUploading={createAndUploadMutation.isPending}
          />

          {pageError ? (
            <div className="mt-4 rounded-2xl bg-rose-500/10 px-4 py-3 text-sm text-rose-200 ring-1 ring-rose-500/30">
              {pageError}
            </div>
          ) : null}
        </section>

        <section className="rounded-3xl bg-background/10 p-6 ring-1 ring-foreground/10 lg:col-span-1">
          <h2 className="text-sm font-semibold">{recentJobsLabel}</h2>
          <div className="mt-4 flex flex-col gap-3">
            {recents.length === 0 ? (
              <div className="text-sm text-foreground/60">
                Create your first job to see status here.
              </div>
            ) : (
              recents.map((job) => (
                <button
                  key={job.jobId}
                  className="flex w-full items-center justify-between gap-3 rounded-2xl bg-background/20 px-4 py-3 text-left ring-1 ring-foreground/10 transition-colors hover:bg-background/30"
                  onClick={() => router.push(`/jobs/${job.jobId}`)}
                  type="button"
                >
                  <div className="min-w-0">
                    <div className="truncate text-sm font-semibold">{job.jobId}</div>
                    <div className="mt-1 text-xs text-foreground/60">
                      {new Date(job.createdAt).toLocaleString()}
                    </div>
                  </div>
                  <span className="text-xs text-foreground/70">
                    {job.status === "queued" ? "Queued" : job.status}
                  </span>
                </button>
              ))
            )}
          </div>
        </section>
      </div>
    </main>
  );
}


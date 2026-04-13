"use client";

import { useEffect, useMemo, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import UploadDropzone from "@/components/UploadDropzone";
import Button from "@/components/Button";
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
  // Empty on first paint so SSR and hydration match; localStorage only after mount.
  const [recents, setRecents] = useState<RecentJob[]>([]);
  const [pageError, setPageError] = useState<string | null>(null);
  const [showRecents, setShowRecents] = useState(false);

  useEffect(() => {
    queueMicrotask(() => {
      setRecents(loadRecents());
    });
  }, []);

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
      console.log("[Shortcut] upload complete, navigating to job", jobId);
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
      console.error("[Shortcut] upload failed", e);
      setPageError(e instanceof Error ? e.message : "Upload failed.");
    }
  }

  return (
    <main className="mx-auto w-full max-w-7xl flex-1 px-6 py-10">
      <div className="mx-auto flex max-w-4xl flex-col gap-6">
        <header className="text-center animate-fade-in">
          <h1 className="text-4xl font-semibold tracking-tight text-foreground sm:text-5xl">
            Your AI video co-pilot
          </h1>
          <p className="mx-auto mt-3 max-w-2xl text-sm text-muted-foreground sm:text-base">
            Drop one file and Shotcut AI handles silence cleanup, pacing, hooks, captions, and a
            rough cut export you can iterate on instantly.
          </p>
        </header>

        <section className="animate-slide-up">
          <UploadDropzone onUpload={handleUpload} isUploading={createAndUploadMutation.isPending} />
          {pageError ? (
            <div className="mt-4 rounded-2xl bg-error/10 px-4 py-3 text-sm text-error ring-1 ring-error/30">
              {pageError}
            </div>
          ) : null}
        </section>

        <section className="panel-surface rounded-3xl p-5">
          <div className="mb-4 text-sm font-semibold text-foreground/90">AI pipeline preview</div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-4">
            {[
              "1. Silence analysis",
              "2. Best-take ranking",
              "3. Caption timing",
              "4. Export rough cut",
            ].map((label, idx) => (
              <div key={label} className="rounded-2xl bg-surface-2/70 px-3 py-2 text-xs text-muted-foreground">
                <div className="mb-2 h-1.5 rounded-full bg-surface-3">
                  <div
                    className="h-full rounded-full bg-gradient-to-r from-accent to-accent-2"
                    style={{ width: idx === 0 && createAndUploadMutation.isPending ? "60%" : "20%" }}
                  />
                </div>
                {label}
              </div>
            ))}
          </div>
        </section>
      </div>

      <aside className="fixed bottom-5 right-5 z-30 max-w-sm">
        <div className="panel-surface rounded-2xl p-3">
          <div className="flex items-center justify-between gap-3">
            <div className="text-xs font-semibold text-foreground/85">{recentJobsLabel}</div>
            <Button variant="ghost" onClick={() => setShowRecents((v) => !v)}>
              {showRecents ? "Hide" : "Show"}
            </Button>
          </div>
          {showRecents ? (
            <div className="mt-3 flex max-h-72 flex-col gap-2 overflow-auto">
              {recents.length === 0 ? (
                <div className="text-xs text-muted-foreground">No recent jobs yet.</div>
              ) : (
                recents.map((job) => (
                  <button
                    key={job.jobId}
                    className="rounded-xl bg-surface-2/80 px-3 py-2 text-left transition hover:bg-surface-3/85"
                    onClick={() => router.push(`/jobs/${job.jobId}`)}
                    type="button"
                  >
                    <div className="truncate text-xs font-semibold text-foreground/90">{job.jobId}</div>
                    <div className="mt-0.5 text-[11px] text-muted-foreground">
                      {new Date(job.createdAt).toLocaleString()} - {job.status}
                    </div>
                  </button>
                ))
              )}
            </div>
          ) : null}
        </div>
      </aside>
    </main>
  );
}


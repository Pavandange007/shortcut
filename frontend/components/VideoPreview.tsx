"use client";

import { useEffect, useState } from "react";
import { fetchAuthenticatedMediaObjectUrl } from "@/lib/api-client";

export default function VideoPreview({
  roughCutUrl,
  mediaRevision,
  title = "Rough Cut",
}: {
  roughCutUrl?: string;
  /** When the server replaces the MP4, pass outputs.media_revision so we refetch the blob. */
  mediaRevision?: number;
  title?: string;
}) {
  const [objectUrl, setObjectUrl] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (!roughCutUrl) {
      setObjectUrl(null);
      setLoadError(null);
      setIsLoading(false);
      return;
    }

    let cancelled = false;
    let blobUrl: string | undefined;

    setIsLoading(true);
    setLoadError(null);
    setObjectUrl(null);

    fetchAuthenticatedMediaObjectUrl(roughCutUrl, {
      cacheBust: mediaRevision,
    })
      .then((url) => {
        if (cancelled) {
          URL.revokeObjectURL(url);
          return;
        }
        blobUrl = url;
        setObjectUrl(url);
      })
      .catch((e) => {
        if (!cancelled) {
          setLoadError(e instanceof Error ? e.message : String(e));
        }
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });

    return () => {
      cancelled = true;
      if (blobUrl) URL.revokeObjectURL(blobUrl);
    };
  }, [roughCutUrl, mediaRevision]);

  return (
    <section className="rounded-3xl bg-background/10 p-4 ring-1 ring-foreground/10">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h2 className="text-sm font-semibold">{title}</h2>
        <span className="text-xs text-foreground/60">
          {roughCutUrl
            ? isLoading
              ? "Loading…"
              : loadError
                ? "Load failed"
                : "Ready"
            : "Preview will appear after export"}
        </span>
      </div>

      {loadError ? (
        <div className="flex min-h-[220px] flex-col justify-center rounded-2xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-200">
          <div className="font-semibold">Could not load video</div>
          <p className="mt-2 text-xs text-rose-200/90">
            The rough cut must be fetched with your session token; if this persists, check the
            API and browser network tab.
          </p>
          <pre className="mt-3 max-h-32 overflow-auto whitespace-pre-wrap break-words text-xs text-rose-200/80">
            {loadError}
          </pre>
        </div>
      ) : objectUrl ? (
        <video
          controls
          src={objectUrl}
          className="w-full rounded-2xl ring-1 ring-foreground/10"
        />
      ) : roughCutUrl && isLoading ? (
        <div className="flex min-h-[220px] items-center justify-center rounded-2xl border border-foreground/10 bg-background/20 p-6 text-sm text-foreground/60">
          Loading preview…
        </div>
      ) : (
        <div className="flex min-h-[220px] items-center justify-center rounded-2xl border border-foreground/10 bg-background/20 p-6 text-sm text-foreground/60">
          No video yet.
        </div>
      )}
    </section>
  );
}

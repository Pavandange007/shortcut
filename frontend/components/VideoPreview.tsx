"use client";

import { useEffect, useRef, useState } from "react";
import { fetchAuthenticatedMediaObjectUrl } from "@/lib/api-client";

export default function VideoPreview({
  roughCutUrl,
  mediaRevision,
  title = "Rough Cut",
  seekToMs,
  onSeekConsumed,
  markers = [],
  onMarkerClick,
}: {
  roughCutUrl?: string;
  /** When the server replaces the MP4, pass outputs.media_revision so we refetch the blob. */
  mediaRevision?: number;
  title?: string;
  /** Seek preview to this timestamp (ms). Cleared via onSeekConsumed after applying. */
  seekToMs?: number | null;
  onSeekConsumed?: () => void;
  markers?: { startMs: number; endMs: number; label?: string }[];
  onMarkerClick?: (markerIndex: number) => void;
}) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [objectUrl, setObjectUrl] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [duration, setDuration] = useState(0);
  const [time, setTime] = useState(0);
  const [volume, setVolume] = useState(1);

  useEffect(() => {
    if (!roughCutUrl) {
      return;
    }

    let cancelled = false;
    let blobUrl: string | undefined;

    queueMicrotask(() => {
      if (cancelled) return;
      setIsLoading(true);
      setLoadError(null);
      setObjectUrl(null);
    });

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

  useEffect(() => {
    const el = videoRef.current;
    if (!el) return;
    const onTime = () => setTime(el.currentTime || 0);
    const onDuration = () => setDuration(el.duration || 0);
    const onPlay = () => setIsPlaying(true);
    const onPause = () => setIsPlaying(false);
    el.addEventListener("timeupdate", onTime);
    el.addEventListener("loadedmetadata", onDuration);
    el.addEventListener("play", onPlay);
    el.addEventListener("pause", onPause);
    return () => {
      el.removeEventListener("timeupdate", onTime);
      el.removeEventListener("loadedmetadata", onDuration);
      el.removeEventListener("play", onPlay);
      el.removeEventListener("pause", onPause);
    };
  }, [objectUrl]);

  useEffect(() => {
    if (seekToMs == null || seekToMs < 0) return;
    const el = videoRef.current;
    if (!el || !objectUrl) return;
    try {
      el.currentTime = seekToMs / 1000;
    } catch {
      /* ignore */
    }
    onSeekConsumed?.();
  }, [seekToMs, objectUrl, onSeekConsumed]);

  function formatTime(s: number): string {
    const whole = Math.max(0, Math.floor(s));
    const m = Math.floor(whole / 60);
    const r = whole % 60;
    return `${m}:${String(r).padStart(2, "0")}`;
  }

  return (
    <section className="panel-surface rounded-3xl p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h2 className="text-sm font-semibold text-foreground/90">{title}</h2>
        <span className="text-xs text-muted-foreground">
          {roughCutUrl
            ? isLoading
              ? "Loading…"
              : loadError
                ? "Load failed"
                : "Ready"
            : "Preview will appear after export"}
        </span>
      </div>

      {!roughCutUrl ? (
        <div className="flex min-h-[220px] items-center justify-center rounded-2xl border border-white/10 bg-surface-1/70 p-6 text-sm text-muted-foreground">
          No video yet.
        </div>
      ) : loadError ? (
        <div className="flex min-h-[220px] flex-col justify-center rounded-2xl border border-error/30 bg-error/10 p-4 text-sm text-error">
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
        <div className="group">
          <video ref={videoRef} src={objectUrl} className="w-full rounded-2xl border border-white/10 bg-black/60" />
          <div className="mt-3 rounded-2xl border border-white/10 bg-surface-1/80 p-3 opacity-100 transition group-hover:opacity-100">
            <div className="mb-2 flex items-center gap-2">
              <button
                type="button"
                className="rounded-full bg-surface-3 px-3 py-1 text-xs"
                onClick={() => {
                  const el = videoRef.current;
                  if (!el) return;
                  if (el.paused) void el.play();
                  else el.pause();
                }}
              >
                {isPlaying ? "Pause" : "Play"}
              </button>
              <span className="text-xs text-muted-foreground">
                {formatTime(time)} / {formatTime(duration)}
              </span>
              <button
                type="button"
                className="ml-auto rounded-full bg-surface-3 px-3 py-1 text-xs"
                onClick={() => {
                  const el = videoRef.current;
                  if (!el) return;
                  if (document.fullscreenElement) void document.exitFullscreen();
                  else void el.requestFullscreen();
                }}
              >
                Fullscreen
              </button>
            </div>
            <div className="relative">
              <input
                type="range"
                min={0}
                max={duration || 0}
                step={0.01}
                value={Math.min(time, duration || 0)}
                className="w-full accent-accent"
                onChange={(e) => {
                  const el = videoRef.current;
                  if (!el) return;
                  const v = Number(e.target.value);
                  el.currentTime = v;
                  setTime(v);
                }}
              />
              {duration > 0 ? (
                <div className="pointer-events-none absolute inset-0">
                  {markers.map((m, i) => {
                    const left = `${(m.startMs / 1000 / duration) * 100}%`;
                    return (
                      <button
                        type="button"
                        key={`${m.startMs}-${m.endMs}-${i}`}
                        className="pointer-events-auto absolute top-1/2 h-3 w-1 -translate-y-1/2 rounded-full bg-accent-2"
                        style={{ left }}
                        title={m.label || `Marker ${i + 1}`}
                        onClick={() => {
                          const el = videoRef.current;
                          if (!el) return;
                          el.currentTime = m.startMs / 1000;
                          setTime(m.startMs / 1000);
                          onMarkerClick?.(i);
                        }}
                      />
                    );
                  })}
                </div>
              ) : null}
            </div>
            <div className="mt-2 flex items-center gap-2">
              <span className="text-[11px] text-muted-foreground">Volume</span>
              <input
                type="range"
                min={0}
                max={1}
                step={0.01}
                value={volume}
                className="w-28 accent-accent-2"
                onChange={(e) => {
                  const v = Number(e.target.value);
                  setVolume(v);
                  if (videoRef.current) videoRef.current.volume = v;
                }}
              />
            </div>
          </div>
        </div>
      ) : roughCutUrl && isLoading ? (
        <div className="flex min-h-[220px] items-center justify-center rounded-2xl border border-white/10 bg-surface-1/70 p-6 text-sm text-muted-foreground">
          Loading preview…
        </div>
      ) : (
        <div className="flex min-h-[220px] items-center justify-center rounded-2xl border border-white/10 bg-surface-1/70 p-6 text-sm text-muted-foreground">No video yet.</div>
      )}
    </section>
  );
}

"use client";

import { useEffect, useId, useMemo, useState } from "react";
import type { ChangeEvent, DragEvent } from "react";
import Button from "./Button";

const defaultAccept = [
  "video/mp4",
  "video/quicktime",
  "video/webm",
  "video/x-matroska",
  "video/ogg",
] as const;

function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const idx = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  const value = bytes / Math.pow(1024, idx);
  return `${value.toFixed(value >= 10 || idx === 0 ? 0 : 1)} ${units[idx]}`;
}

function formatSeconds(seconds: number | null): string {
  if (seconds == null || !Number.isFinite(seconds)) return "—";
  const whole = Math.max(0, Math.floor(seconds));
  const mins = Math.floor(whole / 60);
  const secs = whole % 60;
  return `${mins}:${secs.toString().padStart(2, "0")}`;
}

async function getVideoDurationSeconds(file: File): Promise<number | null> {
  const url = URL.createObjectURL(file);
  try {
    const video = document.createElement("video");
    video.preload = "metadata";
    video.src = url;
    await new Promise<void>((resolve, reject) => {
      video.onloadedmetadata = () => resolve();
      video.onerror = () => reject(new Error("Failed to read video metadata."));
    });
    return Number.isFinite(video.duration) ? video.duration : null;
  } finally {
    URL.revokeObjectURL(url);
  }
}

export default function UploadDropzone({
  onUpload,
  isUploading,
  maxSizeMb = 1024,
  acceptMimeTypes = [...defaultAccept],
}: {
  onUpload: (file: File) => Promise<void>;
  isUploading: boolean;
  maxSizeMb?: number;
  acceptMimeTypes?: readonly string[];
}) {
  const [dragActive, setDragActive] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [durationSeconds, setDurationSeconds] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const inputId = useId();

  const acceptAttr = useMemo(() => acceptMimeTypes.join(","), [acceptMimeTypes]);
  const maxBytes = maxSizeMb * 1024 * 1024;

  useEffect(() => {
    let cancelled = false;

    async function run() {
      if (!selectedFile) {
        setDurationSeconds(null);
        return;
      }

      setError(null);
      setDurationSeconds(null);

      if (selectedFile.size > maxBytes) {
        setError(`File is too large. Max size is ${maxSizeMb} MB.`);
        return;
      }

      try {
        const dur = await getVideoDurationSeconds(selectedFile);
        if (!cancelled) setDurationSeconds(dur);
      } catch {
        if (!cancelled) setError("Could not read video duration. You can still upload.");
      }
    }

    void run();
    return () => {
      cancelled = true;
    };
  }, [selectedFile, maxBytes, maxSizeMb]);

  function validateFile(file: File): string | null {
    if (!acceptMimeTypes.includes(file.type)) {
      return `Unsupported file type (${file.type || "unknown"}).`;
    }
    if (file.size > maxBytes) {
      return `File is too large. Max size is ${maxSizeMb} MB.`;
    }
    return null;
  }

  async function handleFile(file: File) {
    const nextError = validateFile(file);
    if (nextError) {
      setError(nextError);
      setSelectedFile(null);
      return;
    }

    setSelectedFile(file);
    setError(null);
  }

  async function onDrop(e: DragEvent) {
    e.preventDefault();
    setDragActive(false);
    const file = e.dataTransfer.files?.[0];
    if (!file) return;
    await handleFile(file);
  }

  async function onChange(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    await handleFile(file);
    e.target.value = "";
  }

  const fileMeta = selectedFile
    ? {
        name: selectedFile.name,
        size: formatBytes(selectedFile.size),
        duration: formatSeconds(durationSeconds),
      }
    : null;

  return (
    <div className="flex w-full flex-col gap-4">
      <div
        role="button"
        tabIndex={0}
        onDragEnter={(e) => {
          e.preventDefault();
          setDragActive(true);
        }}
        onDragOver={(e) => {
          e.preventDefault();
          setDragActive(true);
        }}
        onDragLeave={(e) => {
          e.preventDefault();
          setDragActive(false);
        }}
        onDrop={onDrop}
        className={[
          "relative min-h-[340px] w-full rounded-3xl p-[1px] transition-all duration-300",
          dragActive ? "scale-[1.02] shadow-[0_18px_42px_rgba(124,92,255,0.32)]" : "shadow-elevated",
        ].join(" ")}
      >
        <div
          className={[
            "relative flex h-full min-h-[338px] flex-col items-center justify-center rounded-[23px] border p-8 text-center",
            "bg-gradient-to-b from-surface-2/95 to-surface-1/90",
            dragActive ? "border-accent/80" : "border-white/15",
          ].join(" ")}
        >
          <div
            className={[
              "absolute inset-0 rounded-[23px] bg-gradient-to-r from-accent/30 via-accent-2/20 to-accent/30 opacity-30 transition-opacity",
              dragActive ? "opacity-80" : "",
            ].join(" ")}
            aria-hidden="true"
          />
          <input
            id={inputId}
            className="hidden"
            type="file"
            accept={acceptAttr}
            onChange={onChange}
            disabled={isUploading}
          />

          <svg
            width="72"
            height="72"
            viewBox="0 0 72 72"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            className="relative z-10 mb-3 text-accent-2"
            aria-hidden="true"
          >
            <path
              d="M50 50H22C15.4 50 10 44.6 10 38C10 31.4 15.4 26 22 26C23.2 19.2 29 14 36 14C44 14 50.5 20.5 50.5 28.5C56.3 29.2 61 34.1 61 40C61 45.5 56.5 50 51 50H50Z"
              stroke="currentColor"
              strokeWidth="2.5"
            />
            <path d="M36 28V48" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
            <path
              d="M28 36L36 28L44 36"
              stroke="currentColor"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>

          <div className="relative z-10 flex max-w-xl flex-col gap-2">
            <p className="text-xl font-semibold tracking-tight text-foreground">
              Drop your video here or click to browse
            </p>
            <p className="text-sm text-muted-foreground">
              AI will detect high-impact moments, build a rough cut, and generate frame-accurate
              captions.
            </p>
          </div>

          <div className="relative z-10 mt-4 flex flex-wrap items-center justify-center gap-x-3 gap-y-2 text-xs text-muted-foreground">
            <span>Accepts: {acceptMimeTypes.slice(0, 2).join(", ")}</span>
            <span>Max: {maxSizeMb} MB</span>
          </div>

          <label
            htmlFor={inputId}
            className={`absolute inset-0 cursor-pointer rounded-3xl ${isUploading ? "pointer-events-none" : ""}`}
          />
        </div>
      </div>

      {error ? (
        <div className="rounded-xl bg-rose-500/10 px-4 py-3 text-sm text-rose-200 ring-1 ring-rose-500/30">
          {error}
        </div>
      ) : null}

      {fileMeta ? (
        <div className="animate-slide-up panel-surface flex flex-col gap-3 rounded-2xl p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="min-w-0">
              <div className="truncate text-sm font-semibold text-foreground/95">{fileMeta.name}</div>
              <div className="mt-1 text-xs text-muted-foreground">
                {fileMeta.size} · Duration {fileMeta.duration}
              </div>
            </div>

            <Button
              variant="primary"
              loading={isUploading}
              onClick={() => {
                if (!selectedFile) return;
                void onUpload(selectedFile);
              }}
            >
              {isUploading ? "Processing..." : "Begin Processing"}
            </Button>
          </div>
          {isUploading ? (
            <div className="animate-shimmer relative h-2 overflow-hidden rounded-full bg-surface-3" />
          ) : null}
        </div>
      ) : (
        <div className="text-xs text-muted-foreground">
          Select a video to enable upload.
        </div>
      )}
    </div>
  );
}


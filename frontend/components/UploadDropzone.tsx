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
          "relative flex min-h-[280px] w-full flex-col items-center justify-center gap-3 rounded-3xl border-2 border-dashed p-6 text-center transition-colors",
          dragActive ? "border-foreground/50 bg-foreground/5" : "border-foreground/15 bg-background/10",
        ].join(" ")}
      >
        <input
          id={inputId}
          className="hidden"
          type="file"
          accept={acceptAttr}
          onChange={onChange}
        />

        <svg
          width="54"
          height="54"
          viewBox="0 0 54 54"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          className="mb-1"
          aria-hidden="true"
        >
          <path
            d="M27 9V27"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
          />
          <path
            d="M18 18L27 9L36 18"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <path
            d="M14 29C14 39 20 45 27 45C34 45 40 39 40 29"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
          />
        </svg>

        <div className="flex flex-col gap-2">
          <p className="text-sm font-semibold tracking-wide text-foreground/90">
            Drag and drop a video
          </p>
          <p className="text-sm text-foreground/60">
            or click to browse. We will generate a rough cut with word-timed captions.
          </p>
        </div>

        <div className="mt-2 flex flex-wrap items-center justify-center gap-x-3 gap-y-2 text-xs text-foreground/60">
          <span>Accepts: {acceptMimeTypes.slice(0, 2).join(", ")}</span>
          <span>Max: {maxSizeMb} MB</span>
        </div>

        <label
          htmlFor={inputId}
          className="absolute inset-0 cursor-pointer rounded-3xl"
        >
          {/* click overlay to trigger the hidden file input */}
        </label>
      </div>

      {error ? (
        <div className="rounded-xl bg-rose-500/10 px-4 py-3 text-sm text-rose-200 ring-1 ring-rose-500/30">
          {error}
        </div>
      ) : null}

      {fileMeta ? (
        <div className="flex flex-col gap-2 rounded-2xl bg-foreground/5 p-4 ring-1 ring-foreground/10">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="min-w-0">
              <div className="truncate text-sm font-semibold">{fileMeta.name}</div>
              <div className="mt-1 text-xs text-foreground/60">
                {fileMeta.size} · Duration {fileMeta.duration}
              </div>
            </div>

            <Button
              variant="primary"
              disabled={isUploading}
              onClick={() => {
                if (!selectedFile) return;
                void onUpload(selectedFile);
              }}
            >
              {isUploading ? "Processing..." : "Upload & Create Job"}
            </Button>
          </div>
        </div>
      ) : (
        <div className="text-xs text-foreground/60">
          Select a video to enable upload.
        </div>
      )}
    </div>
  );
}


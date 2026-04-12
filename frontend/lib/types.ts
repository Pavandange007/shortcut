export type JobStepKey = "silence_removal" | "best_take" | "captions" | "export";
export type StepState = "pending" | "running" | "done" | "failed";
export type JobOverallStatus = "queued" | "running" | "completed" | "failed";

export interface JobStep {
  key: JobStepKey;
  label: string;
  state: StepState;
}

export interface Job {
  id: string;
  createdAt: string;
  overallStatus: JobOverallStatus;
  steps: Record<JobStepKey, StepState>;
  outputs?: {
    roughCutUrl?: string;
    burnedCaptionsUrl?: string;
    exportedUrl?: string;
    error?: string;
    error_export?: string;
    error_caption_burn?: string;
    /** Bust `<video>` blob cache when the rough-cut file is replaced. */
    media_revision?: number;
    burnedCaptionsPath?: string | null;
    bestTakeIndex?: number;
    bestTakeExplanation?: string;
  };
}

export interface WordTiming {
  text: string;
  startMs: number;
  endMs: number;
  confidence?: number | null;
  segmentIndex: number;
}

export interface CaptionLine {
  startMs: number;
  endMs: number;
  text: string;
  words: WordTiming[];
}

export interface SilenceSegment {
  startMs: number;
  endMs: number;
}

export interface TimelineSegment {
  startMs: number;
  endMs: number;
  keepAudio: boolean;
  crossfadeToNextMs?: number | null;
}

export interface TranscriptResult {
  words: WordTiming[];
  rawText: string;
}


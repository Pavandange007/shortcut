export type JobStepKey = "silence_removal" | "best_take" | "captions" | "export";
export type StepState = "pending" | "running" | "done" | "failed";
export type JobOverallStatus = "queued" | "running" | "completed" | "failed";

export interface JobStep {
  key: JobStepKey;
  label: string;
  state: StepState;
}

export type AgentBusMessageUi = {
  id: string;
  fromAgent: string;
  toAgent?: string | null;
  type: string;
  payload?: Record<string, unknown>;
  createdAt: string;
};

export type AgentOrchestrationOutput = {
  phase?: string;
  activeAgents?: string[];
  lastMessages?: AgentBusMessageUi[];
  refinementIteration?: number | null;
  maxRefinementIterations?: number | null;
  refinementConverged?: boolean | null;
  finalQualityScore?: number | null;
};

export type ContentMoment = {
  startMs: number;
  endMs: number;
  label?: string;
  impactScore?: number;
  evidence?: string;
};

export type ContentAnalysisOutput = {
  moments: ContentMoment[];
  confidence?: number;
  summary?: string;
};

export type AgentTraceEntry = {
  agent: string;
  ts: string;
  confidence?: number | null;
  summary?: string;
  inputsHash?: string | null;
  cacheHit?: boolean;
};

export type StoryBeatRole =
  | "setup"
  | "tension"
  | "payoff"
  | "cta"
  | "other";

export type StoryBeatOutput = {
  startMs: number;
  endMs: number;
  role?: StoryBeatRole;
  summary?: string;
  confidence?: number;
};

export type StoryAnalysisOutput = {
  beats: StoryBeatOutput[];
  narrativeSummary?: string;
  confidence?: number;
};

export type ViralClipOutput = {
  startMs: number;
  endMs: number;
  viralScore?: number;
  rationale?: string;
  platformRecommendations?: string[];
};

export type ViralAnalysisOutput = {
  clips: ViralClipOutput[];
  confidence?: number;
};

export type TitleHookSetOutput = {
  primaryTitle?: string;
  hooks?: string[];
  abVariants?: string[];
};

export type ClipTitleHooksOutput = {
  clipIndex: number;
  titleHookSet: TitleHookSetOutput;
};

export type TitleHookAnalysisOutput = {
  clips: ClipTitleHooksOutput[];
  confidence?: number;
};

export type QualityReportOutput = {
  pacing?: number;
  clarity?: number;
  hookStrength?: number;
  redundancy?: number;
  recommendations?: string[];
};

export type RefinementIterationOutput = {
  iterationIndex: number;
  timelineDeltaSummary?: string;
  qualityBefore: number;
  qualityAfter: number;
};

export type RefinementJobOutput = {
  iterations: RefinementIterationOutput[];
  finalQualityScore: number;
  converged: boolean;
  confidence?: number | null;
  summary?: string;
  maxIterations?: number;
  lastQuality?: QualityReportOutput | null;
};

export type JobFeedbackPayload = {
  notes?: string;
  audience?: string;
  style?: string;
  mustIncludeMs?: number[];
  mustExcludeMs?: number[];
};

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
    /** Multi-agent pipeline (Phase 1+). */
    agentTrace?: AgentTraceEntry[];
    agentOrchestration?: AgentOrchestrationOutput;
    contentAnalysis?: ContentAnalysisOutput;
    agentPhaseError?: string;
    storyAnalysis?: StoryAnalysisOutput;
    viralAnalysis?: ViralAnalysisOutput;
    titleHookAnalysis?: TitleHookAnalysisOutput;
    refinement?: RefinementJobOutput;
    userFeedback?: JobFeedbackPayload;
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


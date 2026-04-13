"use client";

import type { JobStepKey, StepState } from "../lib/types";
import Tooltip from "./Tooltip";

const stepOrder: JobStepKey[] = [
  "silence_removal",
  "best_take",
  "captions",
  "export",
];

const stepLabels: Record<JobStepKey, string> = {
  silence_removal: "Silence",
  best_take: "Best Take",
  captions: "Captions",
  export: "Export",
};

const stepDescriptions: Record<JobStepKey, string> = {
  silence_removal: "Analyzing audio and removing dead air.",
  best_take: "Selecting strongest takes and pacing.",
  captions: "Generating and timing captions precisely.",
  export: "Rendering your polished rough cut.",
};

export default function JobProgress({
  statusByStep,
}: {
  statusByStep: Partial<Record<JobStepKey, StepState>>;
}) {
  const firstPending = stepOrder.findIndex((key) => (statusByStep[key] ?? "pending") !== "done");
  const progressCount = firstPending === -1 ? stepOrder.length : firstPending;

  return (
    <ol className="relative flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
      <div className="absolute left-2 right-2 top-3 hidden h-px bg-white/10 sm:block" />
      <div
        className="absolute left-2 top-3 hidden h-px bg-gradient-to-r from-accent to-accent-2 transition-all duration-500 sm:block"
        style={{ width: `${Math.max(0, Math.min(100, (progressCount / Math.max(1, stepOrder.length - 1)) * 100))}%` }}
      />
      {stepOrder.map((key, idx) => {
        const state = statusByStep[key] ?? "pending";
        const toneClass =
          state === "done"
            ? "bg-success"
            : state === "running"
              ? "bg-warning animate-pulse-subtle"
              : state === "failed"
                ? "bg-error"
                : "bg-white/35";

        return (
          <li key={key} className="relative z-10 flex flex-1 items-center gap-2 sm:flex-col sm:items-start">
            <div className="panel-surface inline-flex h-7 w-7 items-center justify-center rounded-full">
              <Tooltip content={stepDescriptions[key]}>
                <span className={`h-2.5 w-2.5 rounded-full ${toneClass}`} />
              </Tooltip>
            </div>
            <div>
              <div className="text-xs font-semibold text-foreground/90 sm:text-[11px]">
                {idx + 1}. {stepLabels[key]}
              </div>
              <div className="text-[11px] text-muted-foreground">
                {state === "pending"
                  ? "Pending"
                  : state === "running"
                    ? "Running"
                    : state === "done"
                      ? "Completed"
                      : "Failed"}
              </div>
            </div>
          </li>
        );
      })}
    </ol>
  );
}


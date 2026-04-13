"use client";

import type { ReactNode } from "react";

type BadgeTone = "default" | "success" | "warning" | "error" | "info";

export default function Badge({
  tone = "default",
  children,
}: {
  tone?: BadgeTone;
  children: ReactNode;
}) {
  const map: Record<BadgeTone, string> = {
    default: "bg-surface-2/80 ring-1 ring-white/15 text-foreground/85",
    success: "bg-success/15 ring-1 ring-success/35 text-success",
    warning: "bg-warning/15 ring-1 ring-warning/35 text-warning",
    error: "bg-error/15 ring-1 ring-error/35 text-error",
    info: "bg-info/15 ring-1 ring-info/35 text-info",
  };

  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-3 py-1 text-xs ${map[tone]}`}>
      {children}
    </span>
  );
}


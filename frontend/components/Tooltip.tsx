"use client";

import type { ReactNode } from "react";

export default function Tooltip({
  content,
  children,
}: {
  content: string;
  children: ReactNode;
}) {
  return (
    <span className="group relative inline-flex">
      {children}
      <span className="pointer-events-none absolute bottom-[calc(100%+8px)] left-1/2 z-30 hidden w-max -translate-x-1/2 rounded-lg border border-white/15 bg-surface-3/95 px-2 py-1 text-[11px] text-foreground/85 shadow-lg group-hover:block">
        {content}
      </span>
    </span>
  );
}

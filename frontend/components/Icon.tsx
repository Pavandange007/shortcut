"use client";

import type { ReactNode } from "react";

export default function Icon({
  children,
  size = 18,
  className = "",
}: {
  children: ReactNode;
  size?: number;
  className?: string;
}) {
  return (
    <span
      className={`inline-flex shrink-0 items-center justify-center text-current ${className}`}
      style={{ width: size, height: size }}
      aria-hidden="true"
    >
      {children}
    </span>
  );
}

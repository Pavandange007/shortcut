"use client";

export default function SkeletonLoader({
  className = "",
}: {
  className?: string;
}) {
  return (
    <div
      className={`animate-shimmer rounded-xl bg-gradient-to-r from-surface-1 via-surface-2 to-surface-1 ${className}`}
      aria-hidden="true"
    />
  );
}

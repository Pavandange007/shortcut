"use client";

import type { ReactNode } from "react";

type ButtonVariant = "primary" | "secondary" | "ghost";

export default function Button({
  variant = "primary",
  disabled,
  loading,
  children,
  onClick,
  type = "button",
}: {
  variant?: ButtonVariant;
  disabled?: boolean;
  loading?: boolean;
  children: ReactNode;
  onClick?: () => void;
  type?: "button" | "submit";
}) {
  const base =
    "inline-flex items-center justify-center gap-2 rounded-full px-4 py-2 text-sm font-semibold transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/60 focus-visible:ring-offset-2 focus-visible:ring-offset-background";

  const styles: Record<ButtonVariant, string> = {
    primary:
      "bg-gradient-to-r from-accent to-accent-2 text-white shadow-[0_10px_24px_rgba(59,167,255,0.25)] hover:-translate-y-0.5 hover:shadow-[0_14px_28px_rgba(124,92,255,0.35)]",
    secondary:
      "panel-surface text-foreground/90 hover:-translate-y-0.5 hover:bg-surface-3/70",
    ghost: "text-foreground/80 hover:-translate-y-0.5 hover:bg-surface-2/80",
  };

  const isDisabled = disabled || loading;

  return (
    <button
      type={type}
      className={`${base} ${styles[variant]} ${isDisabled ? "cursor-not-allowed opacity-60" : ""}`}
      disabled={isDisabled}
      onClick={onClick}
    >
      {loading ? (
        <span
          className="inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/60 border-t-transparent"
          aria-hidden="true"
        />
      ) : null}
      {children}
    </button>
  );
}


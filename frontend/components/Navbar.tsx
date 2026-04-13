"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import Icon from "./Icon";

export default function Navbar() {
  const pathname = usePathname();
  const contextLabel = pathname?.startsWith("/jobs/")
    ? "Editing Session"
    : "Upload Studio";

  return (
    <header className="sticky top-0 z-40 w-full border-b border-white/10 glass">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-3">
        <Link href="/upload" className="text-base font-bold tracking-wide">
          <span className="bg-gradient-to-r from-accent to-accent-2 bg-clip-text text-transparent">
            Shotcut AI
          </span>
        </Link>

        <div className="rounded-full border border-white/10 bg-surface-2/60 px-4 py-1.5 text-xs text-muted-foreground">
          {contextLabel}
        </div>

        <div className="flex items-center gap-3">
          <button
            type="button"
            className="inline-flex h-9 w-9 items-center justify-center rounded-full border border-white/10 bg-surface-2/60 text-foreground/80 transition hover:-translate-y-0.5 hover:bg-surface-3"
            aria-label="Preferences"
            title="Preferences"
          >
            <Icon>
              <svg viewBox="0 0 24 24" fill="none" className="h-5 w-5">
                <path
                  d="M12 8.5a3.5 3.5 0 1 0 0 7a3.5 3.5 0 0 0 0-7Z"
                  stroke="currentColor"
                  strokeWidth="1.7"
                />
                <path
                  d="M19.4 15a1 1 0 0 0 .2 1.1l.1.1a1.2 1.2 0 1 1-1.7 1.7l-.1-.1a1 1 0 0 0-1.1-.2a1 1 0 0 0-.6.9V19a1.2 1.2 0 1 1-2.4 0v-.1a1 1 0 0 0-.6-.9a1 1 0 0 0-1.1.2l-.1.1a1.2 1.2 0 1 1-1.7-1.7l.1-.1a1 1 0 0 0 .2-1.1a1 1 0 0 0-.9-.6H5a1.2 1.2 0 1 1 0-2.4h.1a1 1 0 0 0 .9-.6a1 1 0 0 0-.2-1.1l-.1-.1a1.2 1.2 0 1 1 1.7-1.7l.1.1a1 1 0 0 0 1.1.2a1 1 0 0 0 .6-.9V5a1.2 1.2 0 1 1 2.4 0v.1a1 1 0 0 0 .6.9a1 1 0 0 0 1.1-.2l.1-.1a1.2 1.2 0 1 1 1.7 1.7l-.1.1a1 1 0 0 0-.2 1.1a1 1 0 0 0 .9.6H19a1.2 1.2 0 1 1 0 2.4h-.1a1 1 0 0 0-.9.6Z"
                  stroke="currentColor"
                  strokeWidth="1.7"
                />
              </svg>
            </Icon>
          </button>
          <div className="inline-flex h-9 w-9 items-center justify-center rounded-full border border-accent/50 bg-gradient-to-br from-surface-2 to-surface-3 text-xs font-semibold">
            CH
          </div>
        </div>
      </div>
    </header>
  );
}


import type { NextConfig } from "next";
import path from "node:path";
import { fileURLToPath } from "node:url";

// Anchor Turbopack to this app directory, not process.cwd(). Running `next dev` from the
// monorepo root would otherwise resolve `tailwindcss` against the wrong folder and walk up
// to an unrelated package.json (e.g. in the user profile).
const frontendRoot = path.dirname(fileURLToPath(import.meta.url));
const tailwindcssRoot = path.join(frontendRoot, "node_modules", "tailwindcss");

/** Extra dev hosts (comma-separated), e.g. Tailscale or a machine hostname. */
function extraAllowedDevOrigins(): string[] {
  const raw = process.env.NEXT_ALLOWED_DEV_ORIGINS;
  if (raw === undefined || raw.trim() === "") {
    return [];
  }
  return raw
    .split(",")
    .map((s) => s.trim())
    .filter((s) => s.length > 0);
}

const nextConfig: NextConfig = {
  // Opening the app via LAN IP (Next’s “Network” URL) sends that host on the HMR WebSocket
  // Origin; Next blocks it unless listed here. Wildcards match per Next’s allowedDevOrigins rules.
  allowedDevOrigins: [
    "10.*.*.*",
    "192.168.*.*",
    // Docker / 172.16.0.0/12 LANs (dev-only; use NEXT_ALLOWED_DEV_ORIGINS to narrow if needed)
    "172.*.*.*",
    ...extraAllowedDevOrigins(),
  ],
  turbopack: {
    root: frontendRoot,
    // PostCSS still resolved `tailwindcss` from the monorepo parent; force the real install.
    resolveAlias: {
      tailwindcss: tailwindcssRoot,
    },
  },
  webpack: (config) => {
    config.resolve ??= {};
    const { alias } = config.resolve;
    if (alias && typeof alias === "object" && !Array.isArray(alias)) {
      (alias as Record<string, string>)["tailwindcss"] = tailwindcssRoot;
    } else {
      config.resolve.alias = { tailwindcss: tailwindcssRoot };
    }
    return config;
  },
};

export default nextConfig;

# Changelog

All notable changes to this frontend are documented here.

## 2026-04-11

- **Video preview:** rough-cut MP4 is loaded with `fetch` + `Authorization` and a `blob:` URL. `<video src>` does not send Bearer tokens, so `/jobs/{id}/rough-cut` returned 404 for the real `user_id` and the player stayed black at `0:00`.

- Job page: stop `refetchInterval` when the query is in `error` state (fixes endless 404 polling and console spam). Copy for “Job not found” explains in-memory jobs + API restart. `isJobNotFoundError()` helper.

- API client: `serializeUnknownError`; `isJobNotFoundError`; `getJobStatus` no longer logs on failure (job page logs once with dedupe).

- Job page: browser console logs `[Shortcut] job update` on each changed poll (full job object when `error` / `error_export`). Upload: `[Shortcut] upload complete` / `upload failed`. API client logs failed `GET /jobs/{id}`.

- `next.config.ts`: `allowedDevOrigins` for RFC1918-style LAN patterns plus optional `NEXT_ALLOWED_DEV_ORIGINS` so HMR WebSockets work when opening the app via the machine’s “Network” IP (Next otherwise blocks `/_next/*` for non-localhost origins).

- Repo root: added minimal `package.json` so module resolution stops at the monorepo instead of using a `package.json` in the user home directory.

- `next.config.ts`: `turbopack.resolveAlias` and `webpack.resolve.alias` map `tailwindcss` to `frontend/node_modules/tailwindcss` (PostCSS still resolved the package from the wrong directory when only `turbopack.root` was set). Kept `turbopack.root` from `import.meta.url`. Supersedes the 2026-04-05 `process.cwd()`-only approach.

## 2026-04-11

- Upload dropzone: default max file size increased from 500 MB to **1024 MB** (aligned with backend `MAX_UPLOAD_MB`).

- Video preview: pass `outputs.media_revision` into the authenticated media fetch as a cache-bust query param so replacing `rough_cut.mp4` on the server forces a new blob URL.

- Job page: single preview is the captioned rough cut (backend now burns subtitles onto `rough_cut.mp4`). Show `outputs.error_caption_burn` when export succeeded but subtitle burn failed.

## 2026-04-03

- Video preview: resolve relative rough-cut URLs against the configured API base URL.

## 2026-04-05

- Upload page: load `localStorage` recents in `useEffect` so SSR/hydration match (fixes h2 “Recent jobs” mismatch).
- `next.config.ts`: set `turbopack.root` to `process.cwd()` to silence wrong inferred monorepo root. *(Superseded 2026-04-11: cwd breaks when not `frontend/`.)*

- Removed Firecrawl placeholder button from upload page; theme comments updated (no style-crawl integration).

- Job page: show hint while silence-removal/transcription is running (model download + slow CPU).

## 2026-04-04

- Repo layout: app now lives under `Desktop/projects/shortcut/frontend` (monorepo with `backend/`). Run `npm install` here after copy (excluded `node_modules` from copy).

- API client: read `job_id` from `POST /jobs` (was incorrectly expecting `jobId`, which led to `/jobs/undefined/upload` and 404).
- API client: map `GET /jobs/{id}` snake_case fields (`job_id`, `created_at`, `overall_status`) to the frontend `Job` shape.
- Job page: show backend `outputs.error` and `outputs.error_export`; clearer status copy when export is skipped (e.g. FFmpeg missing).

# Changelog

All notable changes to this backend are documented here.

## 2026-04-11

- Repo hygiene: `__pycache__` / `*.pyc` removed from version control; `.gitignore` extended (root `.next/`, `backend/.env`, `!backend/.env.example`). Added root `LICENSE` (MIT), `CONTRIBUTING.md`, `SECURITY.md`.

- Uploads: default max video size is **1024 MB** (frontend dropzone + streaming limit in `POST /jobs/{id}/upload`). Override with `MAX_UPLOAD_MB` in `.env`.

- Caption burn-in: `ffprobe` sets ASS `PlayRes` to the input video size; optional `fontsdir` points at OS fonts (e.g. `%WINDIR%/Fonts` on Windows) so libass can load Arial/glyphs. Thicker outline + `ScaledBorderAndShadow`. `roughCutUrl` and `outputs.media_revision` are set only **after** the burn attempt so clients do not cache a pre-subtitle MP4; empty caption list copies the video without re-encode.

- Pipeline + `POST /jobs/{id}/export`: export silence-stripped `rough_cut.mp4`, then burn captions onto **that** file (word timings remapped from source time to rough-cut time). Single deliverable for preview: `/jobs/{id}/rough-cut`. `POST /jobs/{id}/captions` with `burn_in` re-burns the rough cut when it exists (otherwise burns the full upload). If caption burn fails after export, `outputs.error_caption_burn` is set and the rough cut remains without subtitles.

- FFmpeg **caption burn-in** (Windows): `subtitles` filter now uses `subtitles='C\:/…'` so the drive colon is not parsed as a filter option separator; fixes burn-in failures with exit codes like `4294967274`. `_run_ffmpeg` appends stderr to raised errors for easier diagnosis.

- **Config:** `Settings` now uses `SettingsConfigDict(env_file=backend/.env)` so variables like `FFMPEG_BIN` actually load (previously only process env was read; `.env` was ignored).

- Logging: app lifespan logs `startup: ffmpeg ok|missing` on API boot; export failures use `logger.error` with `outputs.error_export` text. `GET /health` returns `ffmpeg_available` and `ffmpeg_path`.

- FFmpeg: `FFMPEG_BIN` in `.env` for a full path when `ffmpeg` is not on `PATH`. Invalid `FFMPEG_BIN` (e.g. placeholder) falls back to `PATH` with a warning; errors distinguish bad path vs missing entirely. Pipeline uses `ffmpeg_available()` / resolution inside `export_rough_cut` (no duplicate pre-check).

- Whisper: if `WhisperModel` fails to initialize on CUDA (e.g. `unsupported device cuda:0` when drivers/wheels don’t match), automatically reload on **CPU** with `int8` instead of failing the job.

- Documentation: added repo-root [`docs/OVERVIEW.md`](../docs/OVERVIEW.md) (architecture, pipeline, API table, env vars, MVP caveats) and linked it from root [`README.md`](../README.md).

- Monorepo: added repo-root `.cursorignore` so Cursor skips `node_modules`, `.venv`, `.next`, and `backend/data/` (avoids indexing huge trees that can spike RAM and destabilize the editor).

- Whisper: pick CUDA using `ctranslate2.get_cuda_device_count()` when `GPU_DEVICE` is `cuda:*`, so GPU works without installing PyTorch (previously a missing `torch` import forced CPU on NVIDIA GPUs).

- Startup: lazy-import Google Genai inside `gemini_service._get_client()` so a broken or missing `google-genai` install fails on first Gemini use, not on `uvicorn` import.
- Startup: lazy-import `run_job_pipeline` from upload handler so the Whisper/FFmpeg worker graph is not loaded until the first video upload.
- `routes_retakes`: lazy-import `select_best_take` so `/retakes/best` is the first code path that loads `gemini_service`.
- Added `dev.ps1` to always run Uvicorn from `backend/` (fixes `ModuleNotFoundError: No module named 'app'` when the shell cwd is the repo root).

## 2026-04-03

- Whisper: auto-fallback to CPU (`int8`) when CUDA is requested but unavailable.
- Pipeline: if caption grouping/persistence fails, mark job `failed` and stop early.
- Pipeline: if FFmpeg export fails (including missing `ffmpeg` on PATH), keep job `completed` and record `error_export` so transcript/captions remain usable.

## 2026-04-05

- Removed Firecrawl: deleted `firecrawl_service.py`, `routes_style`, `POST /style/sync`, `firecrawl-py` dependency, and `FIRECRAWL_API_KEY` from settings. Theming is manual via `frontend/tailwind.config.js` and `globals.css`.

- Whisper: log model load, transcribe start (file size), periodic segment progress, and total time so long CPU runs are visible in the terminal.

## 2026-04-04

- Project tree copied to `Desktop/projects/shortcut` (monorepo: `frontend/`, `backend/`); removed mistaken nested `backend/backend/` data mirror; added repo root `README.md`, `.gitignore`, and `backend/.env.example`.

- Pipeline: only start work when job status is `queued` (avoids duplicate concurrent runs).
- Pipeline: structured logging to stderr for start, success, transcript failures (`logger.exception`), and export warnings.
- `app.main`: attach `app.*` logger with INFO handler so pipeline logs show even if uvicorn log level is `warning`.

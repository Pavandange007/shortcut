# Shortcut — AI Video Editor MVP

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Monorepo layout:

- **`frontend/`** — Next.js (App Router) upload UI and job status.
- **`backend/`** — FastAPI, faster-whisper, Gemini, FFmpeg pipeline.

## How it works

1. **Browser** — User opens the Next.js app, gets a JWT via `POST /auth/session`, then `POST /jobs` and `POST /jobs/{id}/upload` with the video file.
2. **Background pipeline** (`app/workers/background.py`) runs after upload: **faster-whisper** produces word-level timestamps → **silence heuristics** build `timeline.json` → optional **Gemini** “best take” copy on the single transcript → **caption** lines + optional FFmpeg **burn-in** → FFmpeg **rough cut** from kept timeline segments (needs **FFmpeg** on `PATH` or **`FFMPEG_BIN`** in `.env`).
3. **Storage** — Files live under `backend/data/uploads/{user_id}/{job_id}/` (video, JSON artifacts). Jobs are tracked in an in-memory store (MVP).
4. **Frontend** — `/upload` creates the job and uploads; `/jobs/[jobId]` polls `GET /jobs/{id}` until steps complete and shows preview URL when export succeeds.

Optional: **`GEMINI_API_KEY`** improves best-take text; without it the pipeline still defaults sensibly. **FFmpeg** is required for burned captions and rough-cut MP4 export (install and add to `PATH`, or set **`FFMPEG_BIN`** to `ffmpeg.exe`).

## Prerequisites

- Node.js 20+ (for frontend)
- Python 3.10+ (for backend)
- **FFmpeg** — on `PATH`, or set `FFMPEG_BIN` in `backend/.env` (see `.env.example`). On Windows: `winget install Gyan.FFmpeg` then restart the terminal, or download a build and point `FFMPEG_BIN` at `...\bin\ffmpeg.exe`.
- Optional: CUDA for faster-whisper (`GPU_DEVICE`)

## Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# edit .env — set AUTH_SECRET (32+ chars), API keys as needed
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Windows shortcut (from `backend/`): `.\dev.ps1` starts the same server if `.venv` exists.

## Frontend

```powershell
cd frontend
npm install
# optional: set API URL
# $env:NEXT_PUBLIC_API_BASE_URL="http://127.0.0.1:8000"
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). The UI defaults the API to `http://localhost:8000`.

**Where logs go:** The **FastAPI terminal** logs Whisper, pipeline steps, `startup: ffmpeg …`, and export errors. The **browser DevTools → Console** shows `[Shortcut] job update` / `job update (issues)` with full job JSON when the job page polls (job data is fetched client-side, so it does not appear in the Next.js terminal). `GET /health` includes `ffmpeg_available` and `ffmpeg_path`.

**Frontend troubleshooting:** Run only one `next dev` at a time. If you see `Another next dev server is already running`, stop the other process (or `taskkill /PID <pid> /F` on Windows). If the app errors after crashes or duplicate devs, delete `frontend/.next` and run `npm run dev` again from `frontend/`. If the **HMR WebSocket** fails while using the “Network” URL, use [http://127.0.0.1:3000](http://127.0.0.1:3000) instead, or set `NEXT_ALLOWED_DEV_ORIGINS` (comma-separated hostnames) and ensure `frontend/next.config.ts` `allowedDevOrigins` covers your LAN (private ranges are listed there by default).

## Environment

See `backend/.env.example`. Never commit real `.env` files or `backend/data/` (uploads are local-only).

## Publishing on GitHub

1. Create a new repository (no README/license if you are pushing this tree first).
2. From the repo root: `git remote add origin https://github.com/<you>/<repo>.git` then `git push -u origin main`.
3. Confirm **Settings → Secrets and variables** are empty in the fork; never push `backend/.env`.
4. Optional: enable **Security → Private vulnerability reporting** and adjust `SECURITY.md` if you use a different process.

## License

[MIT](LICENSE).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Documentation

- **[Project overview](docs/OVERVIEW.md)** — architecture, pipeline stages, API summary, configuration, and MVP limitations.

## Changelogs

- `frontend/CHANGELOG.md`
- `backend/CHANGELOG.md`

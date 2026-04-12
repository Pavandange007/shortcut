# Contributing

1. **Fork** the repository and create a branch from `main`.
2. **Backend:** work from `backend/` with a virtualenv; run `pip install -r requirements.txt` and format/lint if you add tooling.
3. **Frontend:** work from `frontend/`; run `npm install` and `npm run build` before opening a PR.
4. **Do not commit** `backend/.env`, API keys, or files under `backend/data/`. Use `backend/.env.example` as the template.
5. Note notable behavior changes in `backend/CHANGELOG.md` and/or `frontend/CHANGELOG.md`.

Pull requests should describe what changed and why in plain language.

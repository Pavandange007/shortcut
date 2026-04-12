# Security

- **Do not** commit real secrets. Keep `backend/.env` local-only (it is gitignored). Rotate any key that was ever committed.
- **Report** suspected vulnerabilities through this repository’s **Security** tab → *Report a vulnerability* (GitHub Private vulnerability reporting), once the repo is on GitHub.

For production, replace the default `AUTH_SECRET`, use HTTPS, and run behind a proper reverse proxy with request size limits appropriate for your deployment.

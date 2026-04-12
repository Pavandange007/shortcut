# Run API from the backend folder so `app` resolves (avoids ModuleNotFoundError).
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    Write-Error "Missing .venv. From this folder run: python -m venv .venv && .\.venv\Scripts\pip install -r requirements.txt"
}
& ".\.venv\Scripts\python.exe" -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

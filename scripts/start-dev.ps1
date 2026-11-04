# start-dev.ps1 - Bootstrap RAGentHub local dev env
# Usage: .\scripts\start-dev.ps1
# Starts the Python AI service only; run `mvn spring-boot:run` in backend-java separately.

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "==> [1/3] Create Python venv" -ForegroundColor Cyan
$venv = Join-Path $root "ai-service\.venv"
if (-not (Test-Path $venv)) {
    python -m venv $venv
}
$py = Join-Path $venv "Scripts\python.exe"

Write-Host "==> [2/3] Install deps (first run is slow)" -ForegroundColor Cyan
& $py -m pip install --upgrade pip
& $py -m pip install -r (Join-Path $root "ai-service\requirements.txt")

Write-Host "==> [3/3] Ingest medical sample corpus and start uvicorn" -ForegroundColor Cyan
Set-Location (Join-Path $root "ai-service")
& $py -m app.scripts.ingest --domain medical
& $py -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
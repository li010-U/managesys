<#
.SYNOPSIS
  Local CI-equivalent: run the full backend test suite (mirrors .github/workflows/ci.yml).
.EXAMPLE
  .\scripts\run_ci.ps1
#>

$ErrorActionPreference = "Stop"
$BackendDir = Split-Path -Parent $PSScriptRoot
$RepoRoot   = Split-Path -Parent $BackendDir
$VenvPy     = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$Python = if (Test-Path $VenvPy) { $VenvPy } else { "python" }
Push-Location $BackendDir
try {
    Write-Host "==> backend pytest" -ForegroundColor Cyan
    & $Python -m pytest -q
    if ($LASTEXITCODE -ne 0) { throw "pytest failed" }
    Write-Host "CI-LOCAL OK (backend)" -ForegroundColor Green
} catch {
    Write-Host ("CI-LOCAL FAIL: " + $_.Exception.Message) -ForegroundColor Red
    exit 1
} finally {
    Pop-Location
}

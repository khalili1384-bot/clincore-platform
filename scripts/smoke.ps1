# scripts/smoke.ps1
# ClinCore automated sanity check — runs pre-release verification.
# Usage: powershell -ExecutionPolicy Bypass -File scripts/smoke.ps1
# Exit code: 0 = all green, 1 = failure.

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$PYTHON = "C:\Users\ZCC\AppData\Local\Programs\Python\Python311\python.exe"
$RepoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

Write-Host "=== ClinCore Smoke Check ===" -ForegroundColor Cyan
Write-Host "Repo: $RepoRoot"
Write-Host ""

# ── 1. Python version ──────────────────────────────────────────────────────
Write-Host "--- Python version ---"
$pyver = & $PYTHON --version 2>&1
Write-Host $pyver
if ($pyver -notmatch "3\.11") {
    Write-Error "FAIL: Python 3.11 required. Got: $pyver"
    exit 1
}
Write-Host "OK: Python 3.11 confirmed" -ForegroundColor Green
Write-Host ""

# ── 2. pip install ─────────────────────────────────────────────────────────
Write-Host "--- pip install -e . ---"
& $PYTHON -m pip install -e . -q
if ($LASTEXITCODE -ne 0) {
    Write-Error "FAIL: pip install failed"
    exit 1
}
Write-Host "OK: pip install succeeded" -ForegroundColor Green
Write-Host ""

# ── 3. alembic upgrade head ────────────────────────────────────────────────
Write-Host "--- alembic upgrade head ---"
Push-Location $RepoRoot
& $PYTHON -m alembic upgrade head
if ($LASTEXITCODE -ne 0) {
    Write-Error "FAIL: alembic upgrade head failed"
    Pop-Location
    exit 1
}
Write-Host "OK: alembic upgrade head succeeded" -ForegroundColor Green
Write-Host ""

# ── 4. alembic head revision ───────────────────────────────────────────────
Write-Host "--- alembic heads ---"
$alembicHead = & $PYTHON -m alembic heads 2>&1
Write-Host $alembicHead
$headMatches = @($alembicHead | Select-String "\(head\)")
$headCount = $headMatches.Count
if ($headCount -ne 1) {
    Write-Error "FAIL: Expected exactly 1 alembic head, found $headCount"
    Pop-Location
    exit 1
}
$revMatch = @($alembicHead | Select-String "([a-f0-9]{12}) \(head\)")
$headRevision = $revMatch[0].Matches[0].Groups[1].Value
Write-Host "OK: Single alembic head: $headRevision" -ForegroundColor Green
Write-Host ""

# ── 5. pytest ──────────────────────────────────────────────────────────────
Write-Host "--- pytest -q ---"
$pytestOutput = & $PYTHON -m pytest -q --tb=short 2>&1
$pytestOutput | ForEach-Object { Write-Host $_ }
if ($LASTEXITCODE -ne 0) {
    Write-Error "FAIL: pytest reported failures"
    Pop-Location
    exit 1
}
$passedLine = $pytestOutput | Select-String "(\d+) passed"
$passedCount = if ($passedLine) { $passedLine.Matches[0].Groups[1].Value } else { "unknown" }
Write-Host "OK: pytest passed ($passedCount tests)" -ForegroundColor Green
Write-Host ""

# ── 6. smoke.py ────────────────────────────────────────────────────────────
Write-Host "--- scripts/smoke.py ---"
& $PYTHON "$RepoRoot\scripts\smoke.py"
if ($LASTEXITCODE -ne 0) {
    Write-Error "FAIL: smoke.py reported failures"
    Pop-Location
    exit 1
}
Write-Host "OK: smoke.py passed" -ForegroundColor Green
Write-Host ""

# ── 7. git tag ─────────────────────────────────────────────────────────────
Write-Host "--- git tag (latest) ---"
$latestTag = & git describe --tags --abbrev=0 2>&1
if ($LASTEXITCODE -ne 0) { $latestTag = "(no tags)" }
Write-Host "Latest tag: $latestTag"
Write-Host ""

# ── 8. working tree status ─────────────────────────────────────────────────
Write-Host "--- git status ---"
$gitStatus = & git status --porcelain=v1 2>&1
$trackedDirty = @($gitStatus | Where-Object { $_ -match "^[MADRCU]" })
$workingTreeClean = if ($trackedDirty.Count -eq 0) { "yes" } else { "no" }

Pop-Location

# ── RELEASE STATUS block ───────────────────────────────────────────────────
Write-Host ""
Write-Host "=== RELEASE STATUS ===" -ForegroundColor Yellow
Write-Host "Alembic head:        $headRevision"
Write-Host "Tests:               $passedCount passed"
Write-Host "Git tag:             $latestTag"
Write-Host "Working tree clean:  $workingTreeClean"
Write-Host "======================" -ForegroundColor Yellow
Write-Host ""

if ($workingTreeClean -eq "no") {
    Write-Host "WARNING: Working tree has uncommitted tracked changes:" -ForegroundColor Yellow
    $trackedDirty | ForEach-Object { Write-Host "  $_" }
}

Write-Host "Smoke check PASSED" -ForegroundColor Green
exit 0

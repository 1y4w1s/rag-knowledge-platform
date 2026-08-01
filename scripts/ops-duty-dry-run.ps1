# Ruige ops duty quartet: orphan + stale + trash purge + chat retention (DRY-RUN ONLY)
# Usage (repo root): .\scripts\ops-duty-dry-run.ps1
# Never passes an apply flag. For real delete/mark-failed, run one CLI by hand after review.
# See docs/tasks/eval-ops-duty-triplet-runbook.md (NW-16 + NW-35)

$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$ScriptsAbs = (Resolve-Path (Join-Path $RepoRoot "backend\scripts")).Path

Set-Location $RepoRoot

function Invoke-DutyDryRun {
    param([Parameter(Mandatory = $true)][string]$ScriptName)

    Write-Host ""
    Write-Host "=== $ScriptName (DRY-RUN only) ===" -ForegroundColor Cyan
    docker compose run --rm --no-deps `
        -v "${ScriptsAbs}:/app/scripts:ro" `
        api python "scripts/$ScriptName"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "FAIL: $ScriptName exit $LASTEXITCODE" -ForegroundColor Red
        exit $LASTEXITCODE
    }
}

Write-Host "=== Ruige ops duty dry-run start ===" -ForegroundColor Cyan
Write-Host "Scripts: $ScriptsAbs"
Write-Host "Mode: DRY-RUN only (wrapper never passes apply flag)"

Invoke-DutyDryRun "scan_orphans.py"
Invoke-DutyDryRun "scan_stale_ingestion.py"
Invoke-DutyDryRun "purge_trash.py"
Invoke-DutyDryRun "purge_chat_threads.py"

Write-Host ""
Write-Host "All four dry-runs finished." -ForegroundColor Green

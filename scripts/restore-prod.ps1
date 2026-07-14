# Eval-Ops M10 · 从 backup-prod.ps1 产出恢复 PostgreSQL + uploads 卷
# 用法：.\scripts\restore-prod.ps1 -BackupDir backups\m10-20260708-223000
# 可选：-SkipHealthCheck（仅恢复、不探活）

param(
    [Parameter(Mandatory = $true)]
    [string]$BackupDir,
    [switch]$SkipHealthCheck,
    [string]$BaseUrl = "http://localhost:8000"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Compose = @("-f", "docker-compose.yml", "-f", "docker-compose.prod.yml")
$ProjectName = Split-Path $Root -Leaf
$UploadsVolume = "${ProjectName}_uploads_data"

function Write-Step([string]$Message) {
    Write-Host "[restore] $Message" -ForegroundColor Cyan
}

function Write-Pass([string]$Message) {
    Write-Host "[restore] OK: $Message" -ForegroundColor Green
}

function Write-Fail([string]$Message) {
    Write-Host "[restore] FAIL: $Message" -ForegroundColor Red
    exit 1
}

function Invoke-Docker([string[]]$DockerArgs) {
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    & docker @DockerArgs 2>&1 | Out-Null
    $code = $LASTEXITCODE
    $ErrorActionPreference = $prev
    return $code
}

function Invoke-DockerCompose([string[]]$ComposeArgs) {
    return (Invoke-Docker -DockerArgs (@("compose") + $Compose + $ComposeArgs))
}

function Resolve-BackupRoot([string]$Dir) {
    if ($Dir -match '[<>|"?*]') {
        Write-Fail @"
BackupDir contains invalid characters (e.g. < >).
Do NOT copy the placeholder literally — use the folder name printed by backup-prod.ps1.

Example:
  .\scripts\restore-prod.ps1 -BackupDir backups\m10-20260708-drill

Recent backups:
$(Get-ChildItem -Directory (Join-Path $Root 'backups') -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 5 |
    ForEach-Object { "  backups\$($_.Name)" } | Out-String)
"@
    }
    if ([System.IO.Path]::IsPathRooted($Dir)) { return $Dir }
    return Join-Path $Root $Dir
}

$backupRoot = Resolve-BackupRoot $BackupDir
$dumpPath = Join-Path $backupRoot "zhiku.dump"
$uploadsTar = Join-Path $backupRoot "uploads.tar.gz"

if (-not (Test-Path $dumpPath)) {
    Write-Fail @"
missing $dumpPath
Run backup first: .\scripts\backup-prod.ps1
Or pick an existing folder under backups\ (see backup complete output).
"@
}
if (-not (Test-Path $uploadsTar)) { Write-Fail "missing $uploadsTar" }

Write-Host "[restore] WARNING: this overwrites DB + uploads volume. Ctrl+C within 5s to abort..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

Write-Step "stop api + web (keep postgres)"
if ((Invoke-DockerCompose @("stop", "api", "web")) -ne 0) { Write-Fail "compose stop failed" }

Write-Step "pg_restore from $dumpPath"
$pgContainer = (docker compose @Compose ps -q postgres 2>$null).Trim()
if (-not $pgContainer) { Write-Fail "postgres container id not found" }
if ((Invoke-Docker -DockerArgs @("cp", $dumpPath, "${pgContainer}:/tmp/zhiku.dump")) -ne 0) {
    Write-Fail "docker cp dump failed"
}
$restoreExit = Invoke-DockerCompose @("exec", "-T", "postgres", "pg_restore", "-U", "zhiku", "-d", "zhiku", "--clean", "--if-exists", "--no-owner", "--no-privileges", "/tmp/zhiku.dump")
Invoke-DockerCompose @("exec", "-T", "postgres", "rm", "-f", "/tmp/zhiku.dump") | Out-Null
if ($restoreExit -gt 1) { Write-Fail "pg_restore failed (exit $restoreExit)" }

Write-Step "extract uploads → volume $UploadsVolume"
$backupUnix = ($backupRoot -replace '\\', '/')
if ((Invoke-Docker -DockerArgs @(
        "run", "--rm",
        "-v", "${UploadsVolume}:/data",
        "-v", "${backupUnix}:/backup:ro",
        "alpine:3.20",
        "sh", "-c", "find /data -mindepth 1 -maxdepth 1 -exec rm -rf {} +; tar xzf /backup/uploads.tar.gz -C /data"
    )) -ne 0) { Write-Fail "uploads extract failed" }

Write-Step "start api + web"
if ((Invoke-DockerCompose @("up", "-d", "api", "web")) -ne 0) { Write-Fail "compose up failed" }

Write-Step "wait for postgres healthy + api ready"
$deadline = (Get-Date).AddSeconds(45)
do {
    Start-Sleep -Seconds 2
    $health = docker compose @Compose ps postgres --format "{{.Health}}" 2>$null
    if ($health -match "healthy") { break }
} while ((Get-Date) -lt $deadline)

if ($SkipHealthCheck) {
    Write-Pass "restore finished (health check skipped)"
    exit 0
}

Write-Step "GET $BaseUrl/health"
Start-Sleep -Seconds 3
try {
    $resp = Invoke-RestMethod -Uri "$BaseUrl/health" -TimeoutSec 20
}
catch {
    Write-Fail "health unreachable: $_"
}

if ($resp.status -ne "ok" -or $resp.database -ne "ok") {
    Write-Fail "health not ok: $($resp | ConvertTo-Json -Compress)"
}

Write-Pass "restore complete — health ok"
Write-Host ($resp | ConvertTo-Json -Compress)

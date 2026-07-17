# Eval-Ops M10 · 生产栈备份：PostgreSQL dump + uploads 命名�?# 前置：docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
# 用法�?\scripts\backup-prod.ps1
#       .\scripts\backup-prod.ps1 -OutDir backups\manual-20260708

param(
    [string]$OutDir = ""
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Compose = @("-f", "docker-compose.yml", "-f", "docker-compose.prod.yml")
$ProjectName = Split-Path $Root -Leaf
$PostgresVolume = "${ProjectName}_postgres_data"
$UploadsVolume = "${ProjectName}_uploads_data"

function Write-Step([string]$Message) {
    Write-Host "[backup] $Message" -ForegroundColor Cyan
}

function Write-Pass([string]$Message) {
    Write-Host "[backup] OK: $Message" -ForegroundColor Green
}

function Write-Fail([string]$Message) {
    Write-Host "[backup] FAIL: $Message" -ForegroundColor Red
    exit 1
}

function Test-DockerVolume([string]$Name) {
    $found = docker volume inspect $Name 2>$null
    return $LASTEXITCODE -eq 0
}

$pgRunning = docker compose @Compose ps --status running --services postgres 2>$null
if (-not $pgRunning) {
    Write-Fail "postgres not running �?start prod stack first (see docs/DEPLOY.md §3.3)"
}

if (-not (Test-DockerVolume $UploadsVolume)) {
    Write-Fail "uploads volume missing: $UploadsVolume �?use prod compose (docker-compose.prod.yml)"
}

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
if ($OutDir) {
    $dest = Join-Path $Root $OutDir
} else {
    $dest = Join-Path $Root "backups\m10-$stamp"
}
New-Item -ItemType Directory -Force -Path $dest | Out-Null

$dumpPath = Join-Path $dest "ruige.dump"
$uploadsTar = Join-Path $dest "uploads.tar.gz"
$manifestPath = Join-Path $dest "manifest.json"

Write-Step "pg_dump �?$dumpPath"
$pgContainer = docker compose @Compose ps -q postgres
if (-not $pgContainer) { Write-Fail "postgres container id not found" }
docker compose @Compose exec -T postgres pg_dump -U ruige -Fc -f /tmp/ruige.dump zhiku
if ($LASTEXITCODE -ne 0) { Write-Fail "pg_dump failed" }
docker cp "${pgContainer}:/tmp/ruige.dump" $dumpPath
if ($LASTEXITCODE -ne 0) { Write-Fail "docker cp dump failed" }
docker compose @Compose exec -T postgres rm -f /tmp/ruige.dump | Out-Null
$dumpSize = (Get-Item $dumpPath).Length
if ($dumpSize -lt 100) { Write-Fail "dump file too small ($dumpSize bytes) �?check postgres logs" }

Write-Step "uploads volume �?$uploadsTar"
$destUnix = ($dest -replace '\\', '/')
docker run --rm `
    -v "${UploadsVolume}:/data:ro" `
    -v "${destUnix}:/backup" `
    alpine:3.20 `
    tar czf /backup/uploads.tar.gz -C /data .
if ($LASTEXITCODE -ne 0) { Write-Fail "uploads tar failed" }

$uploadsSize = (Get-Item $uploadsTar).Length
$manifest = @{
    created_at   = (Get-Date -Format "o")
    project      = $ProjectName
    postgres_vol = $PostgresVolume
    uploads_vol  = $UploadsVolume
    dump_file    = "ruige.dump"
    uploads_file = "uploads.tar.gz"
    dump_bytes   = $dumpSize
    uploads_bytes = $uploadsSize
    compose      = "docker-compose.yml + docker-compose.prod.yml"
    pg_dump_fmt  = "custom (-Fc)"
} | ConvertTo-Json -Depth 3
Set-Content -Path $manifestPath -Value $manifest -Encoding UTF8

Write-Pass "backup complete �?$dest"
Write-Host "  ruige.dump      $dumpSize bytes"
Write-Host "  uploads.tar.gz  $uploadsSize bytes"
Write-Host "  manifest.json"
Write-Host ""
Write-Host "Restore: .\scripts\restore-prod.ps1 -BackupDir `"$dest`""

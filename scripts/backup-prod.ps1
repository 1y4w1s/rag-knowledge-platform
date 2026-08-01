# Ruige backup: PostgreSQL custom dump + uploads volume tar
# Usage: .\scripts\backup-prod.ps1
# Restore: .\scripts\restore-prod.ps1 -BackupFile backups\ruige-yyyyMMdd-HHmmss.sql
# Note: container pg_dump/psql wrappers need -h localhost (B6); file is UTF-8 with BOM (B5).

param(
    [string]$BackupDir = ".\backups",
    [int]$RetentionDays = 30
)

$ErrorActionPreference = "Continue"
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backupPath = Join-Path $BackupDir "ruige-$timestamp.sql"
$uploadBackup = Join-Path $BackupDir "uploads-$timestamp.tar.gz"

# Ensure backup dir exists (absolute path for docker -v on Windows)
New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null
$BackupDirAbs = (Resolve-Path $BackupDir).Path

Write-Host "=== Ruige backup start ===" -ForegroundColor Cyan
Write-Host "Time: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Write-Host "Backup dir: $BackupDirAbs"

# 1. PostgreSQL (-h localhost: avoid cluster wrapper "Invalid data directory")
Write-Host "`n[1/3] PostgreSQL dump..." -ForegroundColor Yellow
docker exec ruige-postgres pg_dump -h localhost -U ruige -d ruige -F c -f /tmp/ruige_backup.dump
if ($LASTEXITCODE -eq 0) {
    docker cp ruige-postgres:/tmp/ruige_backup.dump $backupPath
    docker exec ruige-postgres rm -f /tmp/ruige_backup.dump
    Write-Host "  OK DB: $backupPath" -ForegroundColor Green
} else {
    Write-Host "  FAIL DB dump" -ForegroundColor Red
    exit 1
}

# 2. Uploads volume
Write-Host "[2/3] Uploads tar..."
$uploadsVolume = "rag-knowledge-platform_uploads_data"
docker run --rm -v "${uploadsVolume}:/data" -v "${BackupDirAbs}:/backup" alpine tar czf "/backup/uploads-$timestamp.tar.gz" -C /data .
if ($LASTEXITCODE -eq 0) {
    Write-Host "  OK uploads: $uploadBackup" -ForegroundColor Green
} else {
    Write-Host "  WARN uploads failed (empty volume ok to check manually)" -ForegroundColor Yellow
}

# 3. Retention
Write-Host "[3/3] Cleanup older than $RetentionDays days..."
$cutoff = (Get-Date).AddDays(-$RetentionDays)
Get-ChildItem -Path $BackupDirAbs -Filter "ruige-*.sql" | Where-Object { $_.CreationTime -lt $cutoff } | Remove-Item -Force
Get-ChildItem -Path $BackupDirAbs -Filter "uploads-*.tar.gz" | Where-Object { $_.CreationTime -lt $cutoff } | Remove-Item -Force
Write-Host "  OK cleanup"

# Summary
$dbSize = (Get-Item $backupPath).Length / 1MB
Write-Host "`n=== Backup done ===" -ForegroundColor Cyan
Write-Host "DB dump: $([math]::Round($dbSize, 2)) MB"
Write-Host "Retention: $RetentionDays days"
exit 0

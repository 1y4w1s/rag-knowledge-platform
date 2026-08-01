# Ruige restore: PostgreSQL custom dump (+ optional uploads tar)
# Usage: .\scripts\restore-prod.ps1 -BackupFile .\backups\ruige-yyyyMMdd-HHmmss.sql
# Pair with: -UploadBackup .\backups\uploads-yyyyMMdd-HHmmss.tar.gz
# Note: container pg_restore needs -h localhost (B6); file is UTF-8 with BOM (B5).

param(
    [Parameter(Mandatory = $true)]
    [string]$BackupFile,
    [string]$UploadBackup
)

if (-not (Test-Path $BackupFile)) {
    Write-Host "FAIL backup file missing: $BackupFile" -ForegroundColor Red
    exit 1
}

Write-Host "=== Ruige restore start ===" -ForegroundColor Cyan
Write-Host "Backup file: $BackupFile"
Write-Host "WARN: will overwrite current database!" -ForegroundColor Red
$confirm = Read-Host "Confirm restore? (yes/no)"
if ($confirm -ne "yes") {
    Write-Host "Cancelled"
    exit 0
}

# 1. PostgreSQL (-h localhost: same wrapper trap as pg_dump)
Write-Host "[1/2] Restore PostgreSQL..."
$containerBackup = "/tmp/restore_backup.dump"
docker cp $BackupFile "ruige-postgres:$containerBackup"
docker exec ruige-postgres pg_restore -h localhost -U ruige -d ruige --clean --if-exists $containerBackup
if ($LASTEXITCODE -eq 0) {
    Write-Host "  OK DB restore" -ForegroundColor Green
} else {
    Write-Host "  FAIL DB restore" -ForegroundColor Red
}
docker exec ruige-postgres rm -f $containerBackup

# 2. Uploads (optional)
if ($UploadBackup -and (Test-Path $UploadBackup)) {
    Write-Host "[2/2] Restore uploads..."
    $uploadsVolume = "rag-knowledge-platform_uploads_data"
    $uploadDirAbs = (Get-Item $UploadBackup).Directory.FullName
    $uploadLeaf = Split-Path $UploadBackup -Leaf
    docker run --rm -v "${uploadsVolume}:/data" -v "${uploadDirAbs}:/backup" alpine tar xzf "/backup/$uploadLeaf" -C /data
    Write-Host "  OK uploads restore" -ForegroundColor Green
}

Write-Host "`n=== Restore done ===" -ForegroundColor Cyan
Write-Host "Restart API: docker compose restart api"

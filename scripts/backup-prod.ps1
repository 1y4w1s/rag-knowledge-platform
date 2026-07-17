# 睿阁 — 备份与恢复脚本
# 用法：.\scripts\backup-prod.ps1
# 恢复：.\scripts\restore-prod.ps1 -BackupFile backups\ruige-20260717.sql

param(
    [string]$BackupDir = ".\backups",
    [int]$RetentionDays = 30
)

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backupPath = Join-Path $BackupDir "ruige-$timestamp.sql"
$uploadBackup = Join-Path $BackupDir "uploads-$timestamp.tar.gz"

# 确保备份目录存在
New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null

Write-Host "=== 睿阁 备份开始 ===" -ForegroundColor Cyan
Write-Host "时间: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Write-Host "备份目录: $BackupDir"

# 1. PostgreSQL 备份
Write-Host "`n[1/3] 备份 PostgreSQL..." -ForegroundColor Yellow
docker exec ruige-postgres pg_dump -U ruige -d ruige -F c -f /tmp/ruige_backup.dump
if ($LASTEXITCODE -eq 0) {
    docker cp ruige-postgres:/tmp/ruige_backup.dump $backupPath
    docker exec ruige-postgres rm /tmp/ruige_backup.dump
    Write-Host "  ✅ 数据库备份完成: $backupPath" -ForegroundColor Green
} else {
    Write-Host "  ❌ 数据库备份失败" -ForegroundColor Red
    exit 1
}

# 2. Uploads 文件备份
Write-Host "[2/3] 备份上传文件..."
$uploadsVolume = "rag-knowledge-platform_uploads_data"
docker run --rm -v ${uploadsVolume}:/data -v ${BackupDir}:/backup alpine tar czf /backup/uploads-$timestamp.tar.gz -C /data .
if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✅ 文件备份完成: $uploadBackup" -ForegroundColor Green
} else {
    Write-Host "  ⚠️  文件备份失败（可能无文件）" -ForegroundColor Yellow
}

# 3. 清理旧备份
Write-Host "[3/3] 清理 $RetentionDays 天前的旧备份..."
$cutoff = (Get-Date).AddDays(-$RetentionDays)
Get-ChildItem -Path $BackupDir -Filter "ruige-*.sql" | Where-Object { $_.CreationTime -lt $cutoff } | Remove-Item -Force
Get-ChildItem -Path $BackupDir -Filter "uploads-*.tar.gz" | Where-Object { $_.CreationTime -lt $cutoff } | Remove-Item -Force
Write-Host "  ✅ 清理完成"

# 摘要
$dbSize = (Get-Item $backupPath).Length / 1MB
Write-Host "`n=== 备份完成 ===" -ForegroundColor Cyan
Write-Host "数据库备份: $([math]::Round($dbSize, 2)) MB"
Write-Host "保留天数: $RetentionDays 天"

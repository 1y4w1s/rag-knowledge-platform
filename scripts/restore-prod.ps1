# 睿阁 — 恢复脚本
# 用法：.\scripts\restore-prod.ps1 -BackupFile .\backups\ruige-20260717.sql

param(
    [Parameter(Mandatory = $true)]
    [string]$BackupFile,
    [string]$UploadBackup
)

if (-not (Test-Path $BackupFile)) {
    Write-Host "❌ 备份文件不存在: $BackupFile" -ForegroundColor Red
    exit 1
}

Write-Host "=== 睿阁 恢复开始 ===" -ForegroundColor Cyan
Write-Host "备份文件: $BackupFile"
Write-Host "警告：将覆盖当前数据库！" -ForegroundColor Red
$confirm = Read-Host "确认恢复？(yes/no)"
if ($confirm -ne "yes") {
    Write-Host "已取消"
    exit 0
}

# 1. 恢复 PostgreSQL
Write-Host "[1/2] 恢复 PostgreSQL..."
$containerBackup = "/tmp/restore_backup.dump"
docker cp $BackupFile "ruige-postgres:$containerBackup"
docker exec ruige-postgres pg_restore -U ruige -d ruige --clean --if-exists $containerBackup
if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✅ 数据库恢复成功" -ForegroundColor Green
} else {
    Write-Host "  ❌ 数据库恢复失败" -ForegroundColor Red
}
docker exec ruige-postgres rm -f $containerBackup

# 2. 恢复 Uploads（可选）
if ($UploadBackup -and (Test-Path $UploadBackup)) {
    Write-Host "[2/2] 恢复上传文件..."
    $uploadsVolume = "rag-knowledge-platform_uploads_data"
    docker run --rm -v ${uploadsVolume}:/data -v (Get-Item $UploadBackup).Directory.FullName:/backup alpine tar xzf "/backup/$(Split-Path $UploadBackup -Leaf)" -C /data
    Write-Host "  ✅ 文件恢复成功" -ForegroundColor Green
}

Write-Host "`n=== 恢复完成 ===" -ForegroundColor Cyan
Write-Host "请重启 API 容器: docker compose restart api"

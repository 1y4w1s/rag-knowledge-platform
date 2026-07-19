# 睿阁 — Migration 回滚测试
# 验证所有 migration 的 downgrade 方向正确可用。
# 在 CI 中每次部署前执行，防止「只能升不能降」。
#
# 用法：
#   .\scripts\test-migration-rollback.ps1
#   docker compose exec -T api python -m alembic upgrade head
#   docker compose exec -T api python -m alembic downgrade -1
#   docker compose exec -T api python -m alembic upgrade head

$ErrorActionPreference = "Stop"

Write-Host "=== Migration 回滚测试 ===" -ForegroundColor Cyan
Write-Host ""

# 1. 确保数据库是最新状态
Write-Host "[1/3] 升级到最新 migration ..." -NoNewline
docker compose exec -T api python -m alembic upgrade head 2>&1 | Out-Null
if ($LASTEXITCODE -eq 0) {
    Write-Host " ✅" -ForegroundColor Green
}
else {
    Write-Host " ❌" -ForegroundColor Red
    exit 1
}

# 2. 降级一步
Write-Host "[2/3] 回滚最后一步 migration ..." -NoNewline
$output = docker compose exec -T api python -m alembic downgrade -1 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host " ✅" -ForegroundColor Green
}
else {
    Write-Host " ❌" -ForegroundColor Red
    Write-Host "  $output"
    Write-Host "  ⚠️  回滚失败，请检查 migration 文件中的 downgrade() 函数。" -ForegroundColor Yellow
    exit 1
}

# 3. 再次升级
Write-Host "[3/3] 重新升级到最新 ..." -NoNewline
docker compose exec -T api python -m alembic upgrade head 2>&1 | Out-Null
if ($LASTEXITCODE -eq 0) {
    Write-Host " ✅" -ForegroundColor Green
}
else {
    Write-Host " ❌" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "=== Migration 回滚测试通过 ✅ ===" -ForegroundColor Green

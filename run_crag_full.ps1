# 睿阁 CRAG 全量评测 — 一键运行
# 用法: 在项目根目录执行
#     .\run_crag_full.ps1

$LogFile = "backend\benchmark_results\crag_full_$(Get-Date -Format 'yyyyMMdd_HHmmss').log"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  睿阁 CRAG 全量评测" -ForegroundColor Cyan
Write-Host "  日志: $LogFile" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# 检查 API
$health = curl.exe -s http://localhost:8000/health 2>$null
if ($health -match '"database":"ok"') {
    Write-Host "[OK] API 正常" -ForegroundColor Green
} else {
    Write-Host "[ERROR] API 不可用！请确保 Docker 已启动" -ForegroundColor Red
    pause
    exit 1
}

Write-Host "[$(Get-Date -Format 'HH:mm:ss')] 启动评测..." -ForegroundColor Yellow
Write-Host ""

# 运行评测（输出到控制台，同时写入日志）
python backend\tests\benchmark\tests\run_crag_full_auto.py 2>&1 | Tee-Object -FilePath $LogFile

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  完成！" -ForegroundColor Cyan
Write-Host "  日志: $LogFile" -ForegroundColor Cyan
Write-Host "  报告: backend\benchmark_results\crag_full_result.json" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

pause

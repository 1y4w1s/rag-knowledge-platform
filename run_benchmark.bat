@"
:: 睿阁 CRAG 全量评测脚本
:: 用法：双击运行，或在终端执行
:: 运行前确保 Docker 已启动，API 可访问
:: 日志输出到 benchmark_results/crag_full_YYYYMMDD_HHMMSS.log

@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

set LOG_DIR=backend\benchmark_results
if not exist %LOG_DIR% mkdir %LOG_DIR%

set TIMESTAMP=%DATE:~0,4%%DATE:~5,2%%DATE:~8,2%_%TIME:~0,2%%TIME:~3,2%%TIME:~6,2%
set TIMESTAMP=!TIMESTAMP: =0!
set LOG_FILE=%LOG_DIR%\crag_full_!TIMESTAMP!.log

echo ============================================
echo   睿阁 CRAG 全量评测
echo   日志: %LOG_FILE%
echo ============================================
echo.

echo [%TIME%] 检查 API 状态... >> %LOG_FILE%
curl.exe -s http://localhost:8000/health >nul 2>&1
if !ERRORLEVEL! neq 0 (
    echo [ERROR] API 不可用，请确保 Docker 已启动
    echo [ERROR] API 不可用 >> %LOG_FILE%
    pause
    exit /b 1
)
echo [OK] API 正常 >> %LOG_FILE%

echo [%TIME%] 启动 Python 评测脚本...
echo [%TIME%] 启动 Python 评测脚本 >> %LOG_FILE%

cd /d "%~dp0"
python backend\tests\benchmark\tests\run_crag_full_auto.py 2>&1 >> %LOG_FILE%

echo.
echo ============================================
echo   完成! 查看日志: %LOG_FILE%
echo ============================================
pause
"@

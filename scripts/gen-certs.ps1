# 睿阁 — 自签 HTTPS 证书生成
# 用于内网部署，非生产公网环境。
# 用法：.\scripts\gen-certs.ps1
#
# 生成文件：
#   docker/nginx/certs/ruige.crt    — 自签证书（PEM）
#   docker/nginx/certs/ruige.key    — 私钥
#
# 警告：自签证书不会被浏览器信任，需要手动导入或添加例外。

$ErrorActionPreference = "Stop"
$certsDir = "docker/nginx/certs"

# 创建证书目录
if (-not (Test-Path $certsDir)) {
    New-Item -ItemType Directory -Path $certsDir -Force | Out-Null
    Write-Host "  created $certsDir" -ForegroundColor Green
}

$crtPath = Join-Path $certsDir "ruige.crt"
$keyPath = Join-Path $certsDir "ruige.key"

# 检查是否已存在
if ((Test-Path $crtPath) -and (Test-Path $keyPath)) {
    Write-Host "⚠️  证书已存在，跳过生成。如需重新生成，请先删除：" -ForegroundColor Yellow
    Write-Host "    Remove-Item $crtPath, $keyPath"
    exit 0
}

# 检查 openssl 可用性
$openssl = Get-Command "openssl" -ErrorAction SilentlyContinue
if (-not $openssl) {
    Write-Host "❌ 未找到 openssl。请安装 OpenSSL：" -ForegroundColor Red
    Write-Host "   Windows: choco install openssl 或 https://slproweb.com/products/Win32OpenSSL.html"
    Write-Host "   macOS:   brew install openssl"
    Write-Host "   Linux:   apt install openssl"
    exit 1
}

Write-Host "正在生成自签证书 ..." -ForegroundColor Cyan

# 生成私钥和自签证书（有效期 365 天）
& openssl req -x509 -newkey rsa:2048 -keyout $keyPath -out $crtPath -days 365 -nodes `
    -subj "/C=CN/ST=Guangdong/L=Shenzhen/O=Ruige/CN=localhost" `
    -addext "subjectAltName=DNS:localhost,IP:127.0.0.1" 2>$null

if ($LASTEXITCODE -eq 0) {
    Write-Host "  $crtPath" -ForegroundColor Green
    Write-Host "  $keyPath" -ForegroundColor Green
    Write-Host "✅ 自签证书已生成（有效期 365 天）" -ForegroundColor Green
    Write-Host ""
    Write-Host "部署方式：" -ForegroundColor Cyan
    Write-Host "  1. docker compose down"
    Write-Host "  2. docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build"
    Write-Host "  3. 浏览器访问 https://localhost"
    Write-Host ""
    Write-Host "浏览器会警告证书不受信任，选择「高级 → 继续访问」即可。" -ForegroundColor Yellow
}
else {
    Write-Host "❌ 证书生成失败" -ForegroundColor Red
    exit 1
}

# 睿阁 — 生产密钥初始化检查
# 在首次部署或更新 .env 后运行，验证密钥安全配置。
# 用法：.\scripts\init-secrets.ps1
#
# 检查清单：
#   ✅ .env 存在且不在 .gitignore 外
#   ✅ 关键密钥已从 "changeme" 替换
#   ✅ 文件权限受限（仅当前用户可读）
#   ✅ Docker secrets 兼容格式

param(
    [switch]$Fix,
    [string]$EnvFile = ".env"
)

$ErrorActionPreference = "Stop"
$issues = @()

# ── 1. 检查 .env 是否存在 ──
if (-not (Test-Path $EnvFile)) {
    Write-Host "❌ .env 文件不存在。请复制 .env.production.example 为 .env 并填入密钥。" -ForegroundColor Red
    Write-Host "    cp .env.production.example .env"
    exit 1
}
Write-Host "✅ .env 文件存在" -ForegroundColor Green

# ── 2. 检查关键密钥是否还是占位符 ──
$content = Get-Content $EnvFile -Raw
$criticalKeys = @{
    "POSTGRES_PASSWORD=changeme"    = "POSTGRES_PASSWORD"
    "JWT_SECRET=changeme"           = "JWT_SECRET"
    "DEEPSEEK_API_KEY="             = "DEEPSEEK_API_KEY"
    "TONGYI_API_KEY="               = "TONGYI_API_KEY"
}

$emptyKeys = @()
$placeholderKeys = @()

foreach ($pattern in $criticalKeys.Keys) {
    $keyName = $criticalKeys[$pattern]
    $value = ($content -split "`n" | Where-Object { $_ -match "^$keyName=" }) -replace "^$keyName=", "" -replace "`r", ""
    if ([string]::IsNullOrWhiteSpace($value)) {
        $emptyKeys += $keyName
    }
    elseif ($value -eq "changeme") {
        $placeholderKeys += $keyName
    }
}

if ($emptyKeys.Count -gt 0) {
    $issues += "空密钥: $($emptyKeys -join ', ')"
    Write-Host "⚠️  空密钥: $($emptyKeys -join ', ') — 未配置，相关功能不可用" -ForegroundColor Yellow
}
else {
    Write-Host "✅ 所有密钥已配置" -ForegroundColor Green
}

if ($placeholderKeys.Count -gt 0) {
    Write-Host "❌ 占位密钥: $($placeholderKeys -join ', ') — 仍为 'changeme'，请替换为真实值" -ForegroundColor Red
    $issues += "占位密钥: $($placeholderKeys -join ', ')"
    if ($Fix) {
        Write-Host "   --Fix 模式不自动生成密钥，请手动修改 .env" -ForegroundColor Yellow
    }
}
else {
    Write-Host "✅ 无占位密钥" -ForegroundColor Green
}

# ── 3. 检查权限（Windows 上检查是否有 Everyone 读取权限） ──
if ($IsWindows -or $env:OS -match "Windows") {
    $acl = icacls $EnvFile 2>$null
    if ($acl -match "Everyone") {
        $issues += "文件权限: Everyone 可读取 .env"
        Write-Host "⚠️  .env 文件 Everyone 可读，建议限制权限" -ForegroundColor Yellow
        if ($Fix) {
            icacls $EnvFile /inheritance:r /grant "${env:USERNAME}:F" 2>$null
            Write-Host "  已限制权限为仅 $env:USERNAME 可访问" -ForegroundColor Green
        }
    }
    else {
        Write-Host "✅ .env 权限已限制" -ForegroundColor Green
    }
}
else {
    $mode = (Get-Item $EnvFile).UnixFileMode
    if ($mode -band 0x004) {
        $issues += "文件权限: .env 对其他用户可读"
        Write-Host "⚠️  .env 对其他用户可读，建议 chmod 600" -ForegroundColor Yellow
        if ($Fix) {
            chmod 600 $EnvFile
            Write-Host "  已执行 chmod 600" -ForegroundColor Green
        }
    }
    else {
        Write-Host "✅ .env 权限 600" -ForegroundColor Green
    }
}

# ── 4. 检查 .env 是否在 .gitignore 中 ──
if (Test-Path ".gitignore") {
    $gi = Get-Content ".gitignore" -Raw
    if ($gi -match "(?m)^\.env$") {
        Write-Host "✅ .env 在 .gitignore 中" -ForegroundColor Green
    }
    else {
        Write-Host "❌ .env 不在 .gitignore 中，有提交风险！" -ForegroundColor Red
        $issues += ".gitignore: .env 未在 .gitignore 中"
        if ($Fix) {
            Add-Content ".gitignore" "`n# 生产密钥文件`n.env"
            Write-Host "  已将 .env 加入 .gitignore" -ForegroundColor Green
        }
    }
}
else {
    Write-Host "⚠️  没有 .gitignore 文件" -ForegroundColor Yellow
}

# ── 汇总 ──
Write-Host ""
if ($issues.Count -eq 0) {
    Write-Host "🎉 密钥检查全部通过，可以部署。" -ForegroundColor Green
    exit 0
}
else {
    Write-Host "⚠️  发现 $($issues.Count) 个问题：" -ForegroundColor Yellow
    foreach ($issue in $issues) {
        Write-Host "  - $issue"
    }
    Write-Host ""
    Write-Host "建议修复后重新运行本脚本。" -ForegroundColor Yellow
    exit 1
}

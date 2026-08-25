# 索隐 — pull base images then canonical Compose stack (base + prod overlay)
# Run: .\scripts\docker-up.ps1
# Equivalent to README: docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

& "$PSScriptRoot\docker-pull.ps1"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env from .env.example — replace POSTGRES_PASSWORD and JWT_SECRET (not placeholders) and set an LLM key." -ForegroundColor Yellow
}

docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Waiting for API health (migrate must complete first)..."
$deadline = (Get-Date).AddSeconds(120)
$ok = $false
while ((Get-Date) -lt $deadline) {
    Start-Sleep -Seconds 5
    try {
        $resp = Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" -TimeoutSec 10
        $resp | ConvertTo-Json -Compress
        if ($resp.database -eq "ok") {
            Write-Host "Install OK: database ok" -ForegroundColor Green
            $ok = $true
            break
        }
        Write-Host "API up but database not ok yet..." -ForegroundColor Yellow
    } catch {
        Write-Host "health not ready yet..." -ForegroundColor DarkGray
    }
}
if (-not $ok) {
    Write-Host "health check failed - see: docker compose -f docker-compose.yml -f docker-compose.prod.yml logs api postgres migrate" -ForegroundColor Yellow
}

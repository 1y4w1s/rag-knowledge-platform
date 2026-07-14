# Zhian (知岸) - pull images then docker compose up
# Run: .\scripts\docker-up.ps1

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

& "$PSScriptRoot\docker-pull.ps1"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env - check POSTGRES_PASSWORD and JWT_SECRET" -ForegroundColor Yellow
}

docker compose up -d --build
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Waiting for Postgres healthcheck..."
Start-Sleep -Seconds 8

try {
    $resp = Invoke-RestMethod -Uri "http://localhost:8000/health" -TimeoutSec 10
    $resp | ConvertTo-Json -Compress
    if ($resp.database -eq "ok") {
        Write-Host "Wave 0.2 OK: database ok" -ForegroundColor Green
    } else {
        Write-Host "API up but database not ok - see: docker compose logs api postgres" -ForegroundColor Yellow
    }
} catch {
    Write-Host "health check failed - see: docker compose logs api postgres" -ForegroundColor Yellow
}

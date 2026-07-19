# 睿阁 (Ruige) - pull Docker base images (China mirrors + retry)
# Run from repo root: .\scripts\docker-pull.ps1
# Then: docker compose up -d --build

$ErrorActionPreference = "Continue"

$Images = @(
    @{
        Name    = "postgres:16-bookworm"
        Mirrors = @(
            "docker.m.daocloud.io/library/postgres:16-bookworm"
            "docker.1ms.run/library/postgres:16-bookworm"
            "docker.1panel.live/library/postgres:16-bookworm"
            "postgres:16-bookworm"
        )
    }
    @{
        Name    = "python:3.11-slim"
        Mirrors = @(
            "docker.m.daocloud.io/library/python:3.11-slim"
            "docker.1ms.run/library/python:3.11-slim"
            "docker.1panel.live/library/python:3.11-slim"
            "python:3.11-slim"
        )
    }
)

function Pull-ImageWithFallback {
    param(
        [string]$LocalTag,
        [string[]]$Sources,
        [int]$MaxRetries = 2
    )

    Write-Host ""
    Write-Host "=== Pull $LocalTag ===" -ForegroundColor Cyan

    foreach ($source in $Sources) {
        for ($i = 1; $i -le $MaxRetries; $i++) {
            Write-Host "Try [$i/$MaxRetries]: $source"
            docker pull $source
            if ($LASTEXITCODE -eq 0) {
                if ($source -ne $LocalTag) {
                    docker tag $source $LocalTag
                    if ($LASTEXITCODE -ne 0) {
                        Write-Host "Tag failed: $LocalTag" -ForegroundColor Red
                        return $false
                    }
                }
                Write-Host "OK: $LocalTag" -ForegroundColor Green
                docker images $LocalTag
                return $true
            }
            Write-Host "Failed, retry in 5s..." -ForegroundColor Yellow
            Start-Sleep -Seconds 5
        }
    }

    Write-Host "FAIL: all mirrors failed for $LocalTag" -ForegroundColor Red
    return $false
}

Write-Host "睿阁 (Ruige) Docker image pre-pull" -ForegroundColor Cyan
Write-Host "Tip: apply scripts/docker-engine.example.json in Docker Desktop -> Engine"

docker version *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker not running. Start Docker Desktop first." -ForegroundColor Red
    exit 1
}

Write-Host "Pruning broken build cache..."
docker builder prune -f | Out-Null

$allOk = $true
foreach ($img in $Images) {
    $ok = Pull-ImageWithFallback -LocalTag $img.Name -Sources $img.Mirrors
    if (-not $ok) { $allOk = $false }
}

Write-Host ""
if ($allOk) {
    Write-Host "All images ready. Next:" -ForegroundColor Green
    Write-Host "  docker compose up -d --build"
    Write-Host "  curl http://localhost:8000/health"
    exit 0
}

Write-Host "Some images failed. Try:" -ForegroundColor Yellow
Write-Host "  1. Mobile hotspot or VPN, then re-run this script"
Write-Host "  2. Docker Desktop -> Engine -> Apply mirror config"
Write-Host "  3. Manual: docker pull docker.m.daocloud.io/library/postgres:16-bookworm"
exit 1

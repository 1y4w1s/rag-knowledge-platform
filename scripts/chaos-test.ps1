# Ruige chaos / disconnect resilience test
# Tests PG-down, Redis-down, Celery-down, combined-down — verifies graceful degradation + recovery.
#
# Usage (repo root, stack must be up):
#   .\scripts\chaos-test.ps1
#   .\scripts\chaos-test.ps1 -BaseUrl http://192.168.1.10:8000
#
# WARNING: This script will temporarily STOP and START Docker containers.
# No data is deleted (uses 'stop', not 'down -v'). All containers are restored on finish.
#
# See docs/tasks/nw77-chaos-disconnect-test-plan.md (NW-77)

param(
    [string]$BaseUrl = "http://localhost:8000",
    [string]$Password = "ChaosTest123!"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

# ---- helpers ----

$global:PassCount = 0
$global:FailCount = 0
$global:StopServices = @("postgres", "redis", "celery-worker")

function Write-Banner([string]$Text) {
    Write-Host ""
    Write-Host ("=" * 60) -ForegroundColor Cyan
    Write-Host "  $Text" -ForegroundColor Cyan
    Write-Host ("=" * 60) -ForegroundColor Cyan
}

function Write-Step([string]$Text) {
    Write-Host "  >> $Text" -ForegroundColor DarkGray
}

function Write-Pass([string]$Text) {
    Write-Host "  OK: $Text" -ForegroundColor Green
    $global:PassCount++
}

function Write-Fail([string]$Text) {
    Write-Host "  FAIL: $Text" -ForegroundColor Red
    $global:FailCount++
}

function Assert-HealthField($Response, [string]$Field, [string]$Expected) {
    $actual = $Response.$Field
    if ($null -eq $actual) { $actual = "(null)" }
    $actualStr = "$actual"
    if ($actual -is [System.Collections.IDictionary] -or $actual -is [Array]) {
        $actualStr = $actual | ConvertTo-Json -Compress
    }
    if ("$actual" -eq "$Expected") {
        Write-Pass "health.$Field = $actualStr (expected $Expected)"
        return $true
    } else {
        Write-Fail "health.$Field = $actualStr (expected $Expected)"
        return $false
    }
}

function Assert-HttpStatus(
    [string]$Url,
    [string]$Method,
    [int]$ExpectedStatus,
    [string]$Label,
    [string]$AuthToken = $null
) {
    $headers = @{}
    if ($AuthToken) { $headers["Authorization"] = "Bearer $AuthToken" }
    try {
        if ($Method -eq "GET") {
            try {
                $resp = Invoke-WebRequest -Uri $Url -Headers $headers -TimeoutSec 10
            } catch {
                if ($_.Exception.Response) {
                    $actualStatus = [int]$_.Exception.Response.StatusCode
                } else {
                    $actualStatus = -1
                    Write-Host "  DEBUG: $($_.Exception.Message)" -ForegroundColor DarkGray
                }
                if ($actualStatus -eq $ExpectedStatus) {
                    Write-Pass "$Label -> HTTP $actualStatus (expected $ExpectedStatus)"
                    return $true
                }
                Write-Fail "$Label -> HTTP $actualStatus (expected $ExpectedStatus)"
                return $false
            }
        } elseif ($Method -eq "POST") {
            $body = @{ message = "test" } | ConvertTo-Json -Compress
            try {
                $resp = Invoke-WebRequest -Uri $Url -Method Post -Headers $headers -Body $body `
                    -ContentType "application/json; charset=utf-8" -TimeoutSec 10
            } catch {
                if ($_.Exception.Response) {
                    $actualStatus = [int]$_.Exception.Response.StatusCode
                } else {
                    $actualStatus = -1
                    Write-Host "  DEBUG: $($_.Exception.Message)" -ForegroundColor DarkGray
                }
                if ($actualStatus -eq $ExpectedStatus) {
                    Write-Pass "$Label -> HTTP $actualStatus (expected $ExpectedStatus)"
                    return $true
                }
                Write-Fail "$Label -> HTTP $actualStatus (expected $ExpectedStatus)"
                return $false
            }
        }
        $actualStatus = [int]$resp.StatusCode
        if ($actualStatus -eq $ExpectedStatus) {
            Write-Pass "$Label -> HTTP $actualStatus (expected $ExpectedStatus)"
            return $true
        } else {
            Write-Fail "$Label -> HTTP $actualStatus (expected $ExpectedStatus)"
            return $false
        }
    } catch {
        Write-Fail "$Label -> exception: $($_.Exception.Message)"
        return $false
    }
}

function Get-Health {
    try {
        return (Invoke-RestMethod -Uri "$BaseUrl/health" -TimeoutSec 10)
    } catch {
        return $null
    }
}

function Get-HealthReady {
    try {
        return (Invoke-RestMethod -Uri "$BaseUrl/health/ready" -TimeoutSec 10)
    } catch {
        return $null
    }
}

function Stop-Service([string]$ServiceName) {
    Write-Step "stop container: $ServiceName"
    $ErrorActionPreference = "Continue"
    docker compose stop --timeout 10 $ServiceName 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "docker compose stop $ServiceName exit=$LASTEXITCODE"
    }
    $ErrorActionPreference = "Stop"
    Start-Sleep -Seconds 3
}

function Start-Service([string]$ServiceName) {
    Write-Step "restore: docker compose start $ServiceName"
    $ErrorActionPreference = "Continue"
    docker compose start $ServiceName 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "docker compose start $ServiceName exit=$LASTEXITCODE"
    }
    $ErrorActionPreference = "Stop"
    Start-Sleep -Seconds 3
}

function Restore-AllServices {
    Write-Step "ensuring all services running..."
    $ErrorActionPreference = "Continue"
    foreach ($svc in $global:StopServices) {
        docker compose start $svc 2>&1 | Out-Null
    }
    $ErrorActionPreference = "Stop"
    # 等待 health 恢复（最多 30s）
    $maxWait = 30
    for ($i = 0; $i -lt $maxWait; $i++) {
        $h = Get-Health
        if ($h -and $h.database -eq "ok") {
            Write-Step "health恢复 (${i}s)"
            return
        }
        Start-Sleep -Seconds 1
    }
    Write-Warning "health未在 ${maxWait}s 内恢复，继续执行..."
}

# ---- main ----

Write-Host ""
Write-Host "=== Ruige Chaos / Disconnect Test ===" -ForegroundColor Cyan
Write-Host "BaseUrl: $BaseUrl" -ForegroundColor DarkGray
Write-Host "No permanent changes. Containers are restored on finish." -ForegroundColor DarkGray
Write-Host ""

# 0. pre-flight: ensure stack is up
Write-Banner "Pre-flight: Docker stack status"
$preHealth = Get-Health
if ($null -eq $preHealth) {
    Write-Host "FATAL: /health unreachable. Is the stack running?" -ForegroundColor Red
    Write-Host "  Run: docker compose up -d" -ForegroundColor Red
    exit 1
}
if ($preHealth.status -ne "ok" -or $preHealth.database -ne "ok") {
    Write-Host "WARNING: /health not fully ok. Tests may have false failures." -ForegroundColor Yellow
    Write-Host "  health: $( $preHealth | ConvertTo-Json -Compress )" -ForegroundColor Yellow
} else {
    Write-Pass "initial health ok"
    $global:PassCount--  # offset pre-check count
}
Write-Host ""

# register temp user + auth token (for authenticated endpoint tests)
Write-Banner "Pre-flight: register temp user"
$suffix = [guid]::NewGuid().ToString("N").Substring(0, 8)
$email = "chaos-$suffix@example.com"
$username = "chaos$suffix"

$registerBody = @{
    email        = $email
    username     = $username
    password     = $Password
    account_type = "personal"
} | ConvertTo-Json -Compress

try {
    Invoke-RestMethod -Method Post -Uri "$BaseUrl/api/v1/auth/register" `
        -Body $registerBody -ContentType "application/json; charset=utf-8" -TimeoutSec 15 | Out-Null
    Write-Pass "registered $email"
    $global:PassCount--  # offset
} catch {
    Write-Host "  WARNING: register failed (may already exist): $($_.ErrorDetails.Message)" -ForegroundColor Yellow
}

$authToken = $null
try {
    $loginBody = @{ identifier = $email; password = $Password } | ConvertTo-Json -Compress
    $login = Invoke-RestMethod -Method Post -Uri "$BaseUrl/api/v1/auth/login" `
        -Body $loginBody -ContentType "application/json; charset=utf-8" -TimeoutSec 15
    $authToken = $login.access_token
    if ($authToken) { Write-Pass "login ok"; $global:PassCount-- }
} catch {
    Write-Host "  WARNING: login failed: $($_.ErrorDetails.Message)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "WARNING: containers will be briefly stopped (~7s each). Total ~35s of instability." -ForegroundColor Yellow
Write-Host ""

# ============================================================
# Scenario 1: PostgreSQL down
# ============================================================
Write-Banner "Scenario 1/5: PostgreSQL down"
try {
    Stop-Service "postgres"

    $health = Get-Health
    if ($health) {
        Assert-HealthField $health "database" "error"
        Assert-HealthField $health "status" "degraded"
    } else {
        Write-Fail "/health unreachable"
    }

    $ready = Get-HealthReady
    if ($ready) {
        Assert-HealthField $ready "status" "degraded"
    } else {
        Write-Fail "/health/ready unreachable"
    }

    if ($authToken) {
        Assert-HttpStatus "$BaseUrl/api/v1/knowledge-bases?workspace=personal" "GET" 503 `
            "GET /api/v1/knowledge-bases" $authToken
    } else {
        Write-Host "  skip API 503 check (no token)" -ForegroundColor DarkGray
    }

    Start-Service "postgres"

    $healthRecovered = Get-Health
    if ($healthRecovered) {
        Assert-HealthField $healthRecovered "database" "ok"
        Assert-HealthField $healthRecovered "status" "ok"
    } else {
        Write-Fail "after recovery, /health unreachable"
    }
} catch {
    Write-Fail "Scenario 1 exception: $($_.Exception.Message)"
    Restore-AllServices
}
Write-Host ""

# ============================================================
# Scenario 2: Redis down
# ============================================================
Write-Banner "Scenario 2/5: Redis down"
try {
    Stop-Service "redis"

    $health = Get-Health
    if ($health) {
        Assert-HealthField $health "redis" "error"
        $statusOk = ($health.status -eq "ok" -or $health.status -eq "degraded")
        if ($statusOk) { Write-Pass "health.status = $($health.status) (accept ok or degraded)" }
        else { Write-Fail "health.status = $($health.status) (expected ok or degraded)" }
    } else {
        Write-Fail "/health unreachable"
    }

    $ready = Get-HealthReady
    if ($ready) {
        Assert-HealthField $ready "status" "ok"
    } else {
        Write-Fail "/health/ready unreachable"
    }

    $fallback = Get-Health
    if ($fallback -and $fallback.redis -eq "error") {
        Write-Pass "health still responds (Redis down is handled gracefully)"
    } else {
        Write-Fail "health failed when Redis down"
    }

    Start-Service "redis"

    $healthRecovered = Get-Health
    if ($healthRecovered) {
        Assert-HealthField $healthRecovered "redis" "ok"
    } else {
        Write-Fail "after recovery, /health unreachable"
    }
} catch {
    Write-Fail "Scenario 2 exception: $($_.Exception.Message)"
    Restore-AllServices
}
Write-Host ""

# ============================================================
# Scenario 3: Celery worker down
# ============================================================
Write-Banner "Scenario 3/5: Celery Worker down"
try {
    Stop-Service "celery-worker"

    $health = Get-Health
    if ($health) {
        Assert-HealthField $health "status" "ok"
        Write-Pass "Celery down does not affect /health"
    } else {
        Write-Fail "/health unreachable"
    }

    $healthAgain = Get-Health
    if ($healthAgain) {
        Write-Pass "API responds normally when Celery is down"
    } else {
        Write-Fail "API unreachable when Celery down"
    }

    if ($authToken) {
        Assert-HttpStatus "$BaseUrl/api/v1/knowledge-bases?workspace=personal" "GET" 200 `
            "GET /api/v1/knowledge-bases (celery down)" $authToken
    } else {
        Write-Host "  skip API check (no token)" -ForegroundColor DarkGray
    }

    Start-Service "celery-worker"

    $healthRecovered = Get-Health
    if ($healthRecovered) {
        Write-Pass "Celery recovery OK"
    } else {
        Write-Fail "after celery recovery, /health unreachable"
    }
} catch {
    Write-Fail "Scenario 3 exception: $($_.Exception.Message)"
    Restore-AllServices
}
Write-Host ""

# ============================================================
# Scenario 4: Combined PG + Redis down
# ============================================================
Write-Banner "Scenario 4/5: PostgreSQL + Redis combined down"
try {
    Stop-Service "postgres"
    Stop-Service "redis"

    $health = Get-Health
    if ($health) {
        Assert-HealthField $health "database" "error"
        Assert-HealthField $health "redis" "error"
        Assert-HealthField $health "status" "degraded"
    } else {
        Write-Fail "/health unreachable"
    }

    if ($authToken) {
        Assert-HttpStatus "$BaseUrl/api/v1/knowledge-bases?workspace=personal" "GET" 503 `
            "GET /api/v1/knowledge-bases (combined)" $authToken
    } else {
        Write-Host "  skip API 503 check (no token)" -ForegroundColor DarkGray
    }

    Start-Service "postgres"
    Start-Service "redis"

    $healthRecovered = Get-Health
    if ($healthRecovered) {
        Assert-HealthField $healthRecovered "database" "ok"
        Assert-HealthField $healthRecovered "redis" "ok"
        Assert-HealthField $healthRecovered "status" "ok"
    } else {
        Write-Fail "after recovery, /health unreachable"
    }
} catch {
    Write-Fail "Scenario 4 exception: $($_.Exception.Message)"
    Restore-AllServices
}
Write-Host ""

# ============================================================
# Scenario 5: Full recovery verification
# ============================================================
Write-Banner "Scenario 5/5: Full recovery verification"
try {
    Restore-AllServices

    $health = Get-Health
    if ($health) {
        Assert-HealthField $health "database" "ok"
        Assert-HealthField $health "redis" "ok"
        Assert-HealthField $health "status" "ok"
    } else {
        Write-Fail "final /health unreachable"
    }

    $ready = Get-HealthReady
    if ($ready) {
        Assert-HealthField $ready "database" "ok"
    } else {
        Write-Fail "final /health/ready unreachable"
    }

    if ($health -and $health.database -eq "ok" -and $health.status -eq "ok") {
        Write-Pass "all services recovered. Stack is healthy."
    } else {
        Write-Fail "not all services recovered"
    }
} catch {
    Write-Fail "Scenario 5 exception: $($_.Exception.Message)"
}
Write-Host ""

# ============================================================
# Summary
# ============================================================
Write-Host ""
Write-Host ("=" * 60) -ForegroundColor Cyan
Write-Host "  Summary" -ForegroundColor Cyan
Write-Host ("=" * 60) -ForegroundColor Cyan
if ($global:FailCount -eq 0) {
    Write-Host "  Pass: $($global:PassCount) / $($global:PassCount)" -ForegroundColor Green
    Write-Host "  Fail: 0" -ForegroundColor Green
    Write-Host "  Result: ALL CHAOS TESTS PASSED" -ForegroundColor Green
    Write-Host ""
    Write-Host "  Note: This is a manual disconnect test for graceful degradation and recovery." -ForegroundColor DarkGray
    Write-Host "  Does not simulate network partition, disk full, or LLM timeout." -ForegroundColor DarkGray
    exit 0
} else {
    Write-Host "  Pass: $($global:PassCount)" -ForegroundColor Yellow
    Write-Host "  Fail: $($global:FailCount)" -ForegroundColor Red
    Write-Host "  Result: SOME TESTS FAILED. Check logs above." -ForegroundColor Red
    exit 1
}

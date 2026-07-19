# EW-B3 · 部署 smoke：注册 → 建库 → 上传 → 对话 → 引用非空
# 前置：Docker 栈已起、alembic head、DEEPSEEK + TONGYI Key 已配置
# 用法：.\scripts\smoke-deploy.ps1
#       .\scripts\smoke-deploy.ps1 -BaseUrl http://192.168.1.10:8000

param(
    [string]$BaseUrl = "http://localhost:8000",
    [string]$Password = "SmokeTest123!",
    [int]$PollIntervalSec = 3,
    [int]$PollTimeoutSec = 180
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$FixturePath = Join-Path $PSScriptRoot "fixtures\smoke-handbook.txt"

function Write-Step([string]$Message) {
    Write-Host "[smoke] $Message" -ForegroundColor Cyan
}

function Write-Pass([string]$Message) {
    Write-Host "[smoke] OK: $Message" -ForegroundColor Green
}

function Write-Fail([string]$Message) {
    Write-Host "[smoke] FAIL: $Message" -ForegroundColor Red
    exit 1
}

function Get-DocumentListItems($ListResponse) {
    if ($null -eq $ListResponse) {
        return @()
    }
    if ($ListResponse.PSObject.Properties.Name -contains "items") {
        return @($ListResponse.items)
    }
    return @($ListResponse)
}

function Normalize-SseRaw($Raw) {
    if ($null -eq $Raw) {
        return ""
    }
    if ($Raw -is [System.Array]) {
        $Raw = ($Raw -join "`n")
    }
    return ([string]$Raw).Replace("`r`n", "`n").Trim()
}

function Get-SseDonePayload([string]$Raw) {
    $normalized = Normalize-SseRaw $Raw
    if (-not $normalized) {
        return $null
    }
    $lines = $normalized -split "`n"
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i].Trim() -ne "event: done") {
            continue
        }
        for ($j = $i + 1; $j -lt $lines.Count; $j++) {
            $line = $lines[$j]
            if ($line -like "event: *") {
                break
            }
            if ($line -like "data: *") {
                return ($line.Substring(6).Trim() | ConvertFrom-Json)
            }
        }
    }
    return $null
}

if (-not (Test-Path $FixturePath)) {
    Write-Fail "fixture missing: $FixturePath"
}

Write-Step "health check $BaseUrl/health"
try {
    $health = Invoke-RestMethod -Uri "$BaseUrl/health" -TimeoutSec 15
}
catch {
    Write-Fail "health unreachable — is docker compose up? ($($_.Exception.Message))"
}
if ($health.status -ne "ok" -or $health.database -ne "ok") {
    Write-Fail "health not ok: $($health | ConvertTo-Json -Compress)"
}
Write-Pass "database ok"

$suffix = [guid]::NewGuid().ToString("N").Substring(0, 8)
$email = "smoke-$suffix@example.com"
$username = "smoke$suffix"

Write-Step "register $email"
$registerBody = @{
    email        = $email
    username     = $username
    password     = $Password
    account_type = "personal"
} | ConvertTo-Json -Compress
try {
    Invoke-RestMethod -Method Post -Uri "$BaseUrl/api/v1/auth/register" `
        -Body $registerBody -ContentType "application/json; charset=utf-8" | Out-Null
}
catch {
    Write-Fail "register failed — $($_.ErrorDetails.Message)"
}

Write-Step "login"
$loginBody = @{
    identifier = $email
    password   = $Password
} | ConvertTo-Json -Compress
try {
    $login = Invoke-RestMethod -Method Post -Uri "$BaseUrl/api/v1/auth/login" `
        -Body $loginBody -ContentType "application/json; charset=utf-8"
}
catch {
    Write-Fail "login failed — $($_.ErrorDetails.Message)"
}
$token = $login.access_token
if (-not $token) {
    Write-Fail "login response missing access_token"
}
$authHeader = "Bearer $token"
Write-Pass "logged in as $email"

Write-Step "create knowledge base"
$kbBody = @{ name = "Smoke KB $suffix"; description = "EW-B3 deploy smoke" } | ConvertTo-Json -Compress
try {
    $kb = Invoke-RestMethod -Method Post -Uri "$BaseUrl/api/v1/knowledge-bases?workspace=personal" `
        -Headers @{ Authorization = $authHeader } `
        -Body $kbBody -ContentType "application/json; charset=utf-8"
}
catch {
    Write-Fail "create kb failed — $($_.ErrorDetails.Message)"
}
$kbId = $kb.id
if (-not $kbId) {
    Write-Fail "create kb response missing id"
}
Write-Pass "kb id $kbId"

Write-Step "upload smoke-handbook.txt"
try {
    $uploadJson = curl.exe -sS -X POST "$BaseUrl/api/v1/knowledge-bases/$kbId/documents" `
        -H "Authorization: $authHeader" `
        -F "files=@$FixturePath;type=text/plain"
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "upload curl exit $LASTEXITCODE"
    }
    $upload = $uploadJson | ConvertFrom-Json
}
catch {
    Write-Fail "upload failed — $($_.Exception.Message)"
}
if (-not $upload.documents -or $upload.documents.Count -lt 1) {
    Write-Fail "upload returned no documents"
}
$docId = $upload.documents[0].id
Write-Pass "document id $docId status $($upload.documents[0].status)"

Write-Step "wait for ingestion (timeout ${PollTimeoutSec}s)"
$deadline = (Get-Date).AddSeconds($PollTimeoutSec)
$finalStatus = $null
while ((Get-Date) -lt $deadline) {
    Start-Sleep -Seconds $PollIntervalSec
    try {
        $listResp = Invoke-RestMethod -Uri "$BaseUrl/api/v1/knowledge-bases/$kbId/documents" `
            -Headers @{ Authorization = $authHeader }
    }
    catch {
        Write-Fail "list documents failed — $($_.ErrorDetails.Message)"
    }
    $docs = Get-DocumentListItems $listResp
    $doc = $docs | Where-Object { $_.id -eq $docId } | Select-Object -First 1
    if (-not $doc) {
        Write-Fail "uploaded document not found in list"
    }
    $finalStatus = $doc.status
    Write-Host "  status=$finalStatus chunk_count=$($doc.chunk_count)" -ForegroundColor DarkGray
    if ($finalStatus -eq "completed") { break }
    if ($finalStatus -eq "failed") {
        Write-Fail "ingestion failed: $($doc.error_message)"
    }
}
if ($finalStatus -ne "completed") {
    Write-Fail "ingestion timeout — last status $finalStatus (check TONGYI_API_KEY / docker compose logs api)"
}
Write-Pass "ingestion completed chunk_count=$($doc.chunk_count)"

Write-Step "chat SSE — annual leave question"
$chatBody = '{"message":"\u5458\u5de5\u5e74\u5047\u6709\u51e0\u5929\uff1f"}'
$donePayload = $null
$citationCount = 0
$maxChatAttempts = 5
for ($attempt = 1; $attempt -le $maxChatAttempts; $attempt++) {
    $chatFile = [System.IO.Path]::GetTempFileName()
    $sseFile = [System.IO.Path]::GetTempFileName()
    try {
        [System.IO.File]::WriteAllText(
            $chatFile,
            $chatBody,
            (New-Object System.Text.UTF8Encoding $false)
        )
        curl.exe -sS -X POST "$BaseUrl/api/v1/knowledge-bases/$kbId/chat" `
            -H "Authorization: $authHeader" `
            -H "Content-Type: application/json; charset=utf-8" `
            -H "Accept: text/event-stream" `
            --data-binary "@$chatFile" `
            -o $sseFile | Out-Null
        if ($LASTEXITCODE -ne 0) {
            Write-Fail "chat curl exit $LASTEXITCODE"
        }
        $sseRaw = Normalize-SseRaw ([System.IO.File]::ReadAllText($sseFile, [System.Text.Encoding]::UTF8))
    }
    finally {
        Remove-Item -LiteralPath $chatFile -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $sseFile -Force -ErrorAction SilentlyContinue
    }
    if (-not $sseRaw) {
        Write-Fail "empty chat SSE body (check DEEPSEEK_API_KEY / docker compose logs api)"
    }
    $donePayload = Get-SseDonePayload $sseRaw
    if ($donePayload -and $null -ne $donePayload.citations) {
        $citationCount = @($donePayload.citations).Count
    }
    if ($citationCount -ge 1) {
        break
    }
    if ($attempt -lt $maxChatAttempts) {
        Write-Host "  chat attempt $attempt citations=0 — retry in 2s (embedding index may lag)" -ForegroundColor DarkGray
        Start-Sleep -Seconds 2
    }
}
if (-not $donePayload) {
    $previewLen = [Math]::Min(400, $sseRaw.Length)
    $preview = if ($previewLen -gt 0) { $sseRaw.Substring(0, $previewLen) } else { "(empty)" }
    Write-Fail "chat SSE missing done event — raw: $preview"
}
if ($citationCount -lt 1) {
    Write-Fail "done event has empty citations after $maxChatAttempts attempts — check retrieval / TONGYI embed"
}
Write-Pass "citations=$citationCount message_id=$($donePayload.message_id)"

Write-Host ""
Write-Host "EW-B3 smoke passed: register -> kb -> upload -> chat -> citations" -ForegroundColor Green
exit 0

# V1.0-C4 Canonical Demo (product proof)
# Proves: fresh install -> auth -> KB -> ingest -> index -> grounded Q -> citations
# Does NOT prove: general RAG accuracy, Agent/Critic/L3/L4, model superiority
#
# Prerequisites: Docker Compose canonical install up; chat provider key in .env
# Usage:
#   .\scripts\demo.ps1
#   .\scripts\demo.ps1 -BaseUrl http://127.0.0.1:8000 -SkipCleanup
#   .\scripts\demo.ps1 -SkipUnsupported

param(
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [string]$Password = "CanonicalDemo123!",
    [int]$PollIntervalSec = 3,
    [int]$PollTimeoutSec = 240,
    [switch]$SkipCleanup,
    [switch]$SkipUnsupported,
    [string]$Email = "c4-canonical-demo@example.com",
    [string]$Username = "c4canonical"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$CorpusDir = Join-Path $Root "demo\corpus"
$CorpusFiles = @(
    (Join-Path $CorpusDir "01-leave-policy.txt"),
    (Join-Path $CorpusDir "02-attendance.txt"),
    (Join-Path $CorpusDir "03-office-hours.txt")
)

# Frozen supported case (UTF-8 bytes so WinPS5 parses without mojibake)
# Question: 员工年假有几天？
$SupportedQuestion = [System.Text.Encoding]::UTF8.GetString([byte[]](0xE5,0x91,0x98,0xE5,0xB7,0xA5,0xE5,0xB9,0xB4,0xE5,0x81,0x87,0xE6,0x9C,0x89,0xE5,0x87,0xA0,0xE5,0xA4,0xA9,0xEF,0xBC,0x9F))
$AnswerMustInclude = @("10")
$CitationMustMatchDocName = "01-leave-policy"
# Excerpt hint: 年假
$CitationMustIncludeExcerptHint = [System.Text.Encoding]::UTF8.GetString([byte[]](0xE5,0xB9,0xB4,0xE5,0x81,0x87))

# Frozen unsupported case (no lexical overlap with corpus): 液氮的沸点是多少摄氏度？
$UnsupportedQuestion = [System.Text.Encoding]::UTF8.GetString([byte[]](0xE6,0xB6,0xB2,0xE6,0xB0,0xAE,0xE7,0x9A,0x84,0xE6,0xB2,0xB8,0xE7,0x82,0xB9,0xE6,0x98,0xAF,0xE5,0xA4,0x9A,0xE5,0xB0,0x91,0xE6,0x91,0x84,0xE6,0xB0,0x8F,0xE5,0xBA,0xA6,0xEF,0xBC,0x9F))
$RefuseMarker = [System.Text.Encoding]::UTF8.GetString([byte[]](0xE7,0x9F,0xA5,0xE8,0xAF,0x86,0xE5,0xBA,0x93,0xE4,0xB8,0xAD,0xE6,0x9C,0xAA,0xE6,0x89,0xBE,0xE5,0x88,0xB0,0xE7,0x9B,0xB8,0xE5,0x85,0xB3,0xE5,0x86,0x85,0xE5,0xAE,0xB9))

$script:Results = [ordered]@{}
$script:Results["SYSTEM_REACHABLE"] = "FAIL"
$script:Results["AUTH_OK"] = "FAIL"
$script:Results["DEMO_SCOPE_READY"] = "FAIL"
$script:Results["INGEST_OK"] = "FAIL"
$script:Results["INDEX_READY"] = "FAIL"
$script:Results["QUERY_OK"] = "FAIL"
$script:Results["ANSWER_SEMANTICS_OK"] = "FAIL"
$script:Results["CITATION_PRESENT"] = "FAIL"
$script:Results["CITATION_SOURCE_OK"] = "FAIL"
$script:Results["UNSUPPORTED_CASE_OK"] = "SKIP"

function Write-Step([string]$Message) {
    Write-Host "[demo] $Message" -ForegroundColor Cyan
}

function Write-Layer([string]$Name, [string]$Status, [string]$Detail = "") {
    $script:Results[$Name] = $Status
    $color = "Red"
    if ($Status -eq "PASS") { $color = "Green" }
    elseif ($Status -eq "SKIP") { $color = "DarkYellow" }
    if ($Detail) {
        Write-Host "[demo] $Name=$Status  $Detail" -ForegroundColor $color
    }
    else {
        Write-Host "[demo] $Name=$Status" -ForegroundColor $color
    }
}

function Fail-Demo([string]$Message) {
    Write-Host "[demo] FATAL: $Message" -ForegroundColor Red
    Write-Host ""
    Write-Host "===== Canonical Demo layer summary =====" -ForegroundColor Yellow
    foreach ($k in $script:Results.Keys) {
        Write-Host ("  {0} = {1}" -f $k, $script:Results[$k])
    }
    exit 1
}

function Normalize-SseRaw($Raw) {
    if ($null -eq $Raw) { return "" }
    if ($Raw -is [System.Array]) { $Raw = ($Raw -join "`n") }
    return ([string]$Raw).Replace("`r`n", "`n").Trim()
}

function Get-SseEventPayloads([string]$Raw, [string]$EventName) {
    $normalized = Normalize-SseRaw $Raw
    $out = New-Object System.Collections.Generic.List[object]
    if (-not $normalized) { return @() }
    $lines = $normalized -split "`n"
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i].Trim() -ne "event: $EventName") { continue }
        for ($j = $i + 1; $j -lt $lines.Count; $j++) {
            $line = $lines[$j]
            if ($line -like "event: *") { break }
            if ($line -like "data: *") {
                $json = $line.Substring(6).Trim()
                if ($json) {
                    try { [void]$out.Add(($json | ConvertFrom-Json)) } catch { }
                }
            }
        }
    }
    return @($out.ToArray())
}

function Get-SseAnswerText([string]$Raw) {
    $tokens = Get-SseEventPayloads $Raw "token"
    $parts = New-Object System.Collections.Generic.List[string]
    foreach ($t in $tokens) {
        if ($null -ne $t.text) { [void]$parts.Add([string]$t.text) }
    }
    $corrections = Get-SseEventPayloads $Raw "correction"
    if ($corrections.Count -gt 0 -and $null -ne $corrections[-1].text) {
        return [string]$corrections[-1].text
    }
    return ($parts -join "")
}

function Get-DocumentListItems($ListResponse) {
    if ($null -eq $ListResponse) { return @() }
    if ($ListResponse.PSObject.Properties.Name -contains "items") {
        return @($ListResponse.items)
    }
    return @($ListResponse)
}

function Invoke-ChatSse([string]$KbId, [string]$Token, [string]$Message) {
    $chatFile = [System.IO.Path]::GetTempFileName()
    $sseFile = [System.IO.Path]::GetTempFileName()
    try {
        $bodyObj = (@{ message = $Message } | ConvertTo-Json -Compress)
        [System.IO.File]::WriteAllText(
            $chatFile,
            $bodyObj,
            (New-Object System.Text.UTF8Encoding $false)
        )
        & curl.exe -sS -X POST "$BaseUrl/api/v1/knowledge-bases/$KbId/chat" `
            -H "Authorization: Bearer $Token" `
            -H "Content-Type: application/json; charset=utf-8" `
            -H "Accept: text/event-stream" `
            --data-binary "@$chatFile" `
            -o $sseFile | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw "chat curl exit $LASTEXITCODE"
        }
        return [System.IO.File]::ReadAllText($sseFile, [System.Text.Encoding]::UTF8)
    }
    finally {
        Remove-Item -LiteralPath $chatFile -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $sseFile -Force -ErrorAction SilentlyContinue
    }
}

foreach ($f in $CorpusFiles) {
    if (-not (Test-Path $f)) {
        Fail-Demo "corpus missing: $f"
    }
}

Write-Host ""
Write-Host "===== Suoyin V1.0 Canonical Demo =====" -ForegroundColor White
Write-Host "Interface : repository-owned API script (scripts/demo.ps1)"
Write-Host "Corpus    : demo/corpus (3 TXT files)"
Write-Host "BaseUrl   : $BaseUrl"
Write-Host ""

Write-Step "health $BaseUrl/health"
try {
    $health = Invoke-RestMethod -Uri "$BaseUrl/health" -TimeoutSec 15
}
catch {
    Fail-Demo "health unreachable - is canonical install up? ($($_.Exception.Message))"
}
if ($health.database -ne "ok") {
    Fail-Demo "database not ok: $($health | ConvertTo-Json -Compress)"
}
if ($health.status -ne "ok") {
    Fail-Demo "system degraded (status=$($health.status)) - wait for LLM circuit breaker recovery; do not treat degraded as demo PASS. payload=$($health | ConvertTo-Json -Compress)"
}
Write-Layer "SYSTEM_REACHABLE" "PASS" "database=ok status=ok"

Write-Step "ready check $BaseUrl/health/ready (chat provider key required)"
try {
    $ready = Invoke-RestMethod -Uri "$BaseUrl/health/ready" -TimeoutSec 15
}
catch {
    Fail-Demo "health/ready failed - configure DEEPSEEK_API_KEY (or CHAT_PROVIDER=tongyi + TONGYI_API_KEY) in .env then restart api. ($($_.Exception.Message))"
}
if ($ready.status -ne "ok" -or $ready.api_keys_ok -ne $true) {
    Fail-Demo "chat provider not ready (api_keys_ok=$($ready.api_keys_ok)). Set DEEPSEEK_API_KEY or Tongyi key; embedding default is local BGE (no cloud key)."
}
Write-Host "[demo] provider ready: chat key present (value not printed); embedding expected local BGE" -ForegroundColor DarkGray

# Stable demo identity for repeat runs (avoids register rate-limit on re-run).
# Per-run isolation still comes from a fresh knowledge base (+ cleanup delete).
$suffix = [guid]::NewGuid().ToString("N").Substring(0, 8)
$email = $Email
$username = $Username

Write-Step "auth create-or-login $email"
$loginBody = @{
    identifier = $email
    password   = $Password
} | ConvertTo-Json -Compress
$login = $null
try {
    $login = Invoke-RestMethod -Method Post -Uri "$BaseUrl/api/v1/auth/login" `
        -Body $loginBody -ContentType "application/json; charset=utf-8"
}
catch {
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
        # Already exists / rate-limited: one more login attempt below
        Write-Host "[demo] register note: $($_.ErrorDetails.Message)" -ForegroundColor DarkGray
    }
    try {
        $login = Invoke-RestMethod -Method Post -Uri "$BaseUrl/api/v1/auth/login" `
            -Body $loginBody -ContentType "application/json; charset=utf-8"
    }
    catch {
        Fail-Demo "login failed after create-or-login - $($_.ErrorDetails.Message)"
    }
}
$token = $login.access_token
if (-not $token) {
    Fail-Demo "login response missing access_token"
}
$authHeader = @{ Authorization = "Bearer $token" }
Write-Layer "AUTH_OK" "PASS" "user=$email run=$suffix"

Write-Step "create isolated knowledge base"
$kbBody = @{
    name        = "C4 Canonical Demo $suffix"
    description = "V1.0-C4 repository-owned demo scope (safe to delete)"
} | ConvertTo-Json -Compress
try {
    $kb = Invoke-RestMethod -Method Post `
        -Uri "$BaseUrl/api/v1/knowledge-bases?workspace=personal" `
        -Headers $authHeader `
        -Body $kbBody -ContentType "application/json; charset=utf-8"
}
catch {
    Fail-Demo "create kb failed - $($_.ErrorDetails.Message)"
}
$kbId = $kb.id
if (-not $kbId) {
    Fail-Demo "create kb response missing id"
}
Write-Layer "DEMO_SCOPE_READY" "PASS" "kb_id=$kbId"

Write-Step "upload canonical corpus (3 files)"
$curlArgs = @(
    "-sS", "-X", "POST",
    "$BaseUrl/api/v1/knowledge-bases/$kbId/documents",
    "-H", "Authorization: Bearer $token"
)
foreach ($f in $CorpusFiles) {
    $curlArgs += "-F"
    $curlArgs += "files=@${f};type=text/plain"
}
try {
    $uploadJson = & curl.exe @curlArgs
    if ($LASTEXITCODE -ne 0) {
        Fail-Demo "upload curl exit $LASTEXITCODE"
    }
    $upload = $uploadJson | ConvertFrom-Json
}
catch {
    Fail-Demo "upload failed - $($_.Exception.Message)"
}
if (-not $upload.documents -or @($upload.documents).Count -lt 3) {
    Fail-Demo "upload expected 3 documents, got $(@($upload.documents).Count)"
}
$uploadedIds = @($upload.documents | ForEach-Object { $_.id })
Write-Layer "INGEST_OK" "PASS" "documents=$($uploadedIds.Count)"

Write-Step "wait for indexing (timeout ${PollTimeoutSec}s)"
$deadline = (Get-Date).AddSeconds($PollTimeoutSec)
$allCompleted = $false
$lastSnapshot = ""
$docs = @()
while ((Get-Date) -lt $deadline) {
    Start-Sleep -Seconds $PollIntervalSec
    try {
        $listResp = Invoke-RestMethod `
            -Uri "$BaseUrl/api/v1/knowledge-bases/$kbId/documents" `
            -Headers $authHeader
    }
    catch {
        Fail-Demo "list documents failed - $($_.ErrorDetails.Message)"
    }
    $docs = Get-DocumentListItems $listResp
    $statuses = @()
    $failed = $false
    $failMsg = ""
    foreach ($id in $uploadedIds) {
        $doc = $docs | Where-Object { $_.id -eq $id } | Select-Object -First 1
        if (-not $doc) {
            Fail-Demo "uploaded document $id missing from list"
        }
        $statuses += "$($doc.filename)=$($doc.status)/chunks=$($doc.chunk_count)"
        if ($doc.status -eq "failed") {
            $failed = $true
            $failMsg = "$($doc.filename): $($doc.error_message)"
        }
    }
    $lastSnapshot = ($statuses -join "; ")
    Write-Host "  $lastSnapshot" -ForegroundColor DarkGray
    if ($failed) {
        Fail-Demo "ingestion failed - $failMsg"
    }
    $pending = @($docs | Where-Object { $uploadedIds -contains $_.id -and $_.status -ne "completed" })
    if ($pending.Count -eq 0) {
        $allCompleted = $true
        break
    }
}
if (-not $allCompleted) {
    Fail-Demo "indexing timeout - last: $lastSnapshot"
}
$chunkTotal = 0
foreach ($id in $uploadedIds) {
    $doc = $docs | Where-Object { $_.id -eq $id } | Select-Object -First 1
    if ($doc.chunk_count) { $chunkTotal += [int]$doc.chunk_count }
}
if ($chunkTotal -lt 1) {
    Fail-Demo "indexing completed but chunk_count total is 0"
}
Write-Layer "INDEX_READY" "PASS" "chunk_total=$chunkTotal"

$docsByName = @{}
foreach ($d in $docs) {
    if ($uploadedIds -contains $d.id) {
        $docsByName[$d.filename] = $d.id
    }
}
$leaveDocId = $null
foreach ($name in $docsByName.Keys) {
    if ($name -like "*$CitationMustMatchDocName*") {
        $leaveDocId = $docsByName[$name]
        break
    }
}
if (-not $leaveDocId) {
    Fail-Demo "could not resolve leave-policy document id from filenames: $($docsByName.Keys -join ', ')"
}

Write-Step ("supported question: " + $SupportedQuestion)
$donePayload = $null
$answerText = ""
$citations = @()
$maxChatAttempts = 5
$sseRaw = ""
for ($attempt = 1; $attempt -le $maxChatAttempts; $attempt++) {
    try {
        $sseRaw = Invoke-ChatSse -KbId $kbId -Token $token -Message $SupportedQuestion
    }
    catch {
        Fail-Demo "supported chat failed - $($_.Exception.Message)"
    }
    if (-not (Normalize-SseRaw $sseRaw)) {
        Fail-Demo "empty chat SSE body (check chat provider / api logs)"
    }
    $dones = @(Get-SseEventPayloads $sseRaw "done")
    if ($dones.Count -lt 1) {
        $previewLen = [Math]::Min(400, $sseRaw.Length)
        Fail-Demo "chat SSE missing done event - raw: $($sseRaw.Substring(0, $previewLen))"
    }
    $donePayload = $dones[-1]
    $answerText = Get-SseAnswerText $sseRaw
    $citations = @()
    if ($null -ne $donePayload.citations) {
        $citations = @($donePayload.citations)
    }
    if ($citations.Count -ge 1) { break }
    if ($attempt -lt $maxChatAttempts) {
        Write-Host "  attempt $attempt citations=0 - retry in 2s" -ForegroundColor DarkGray
        Start-Sleep -Seconds 2
    }
}
Write-Layer "QUERY_OK" "PASS" "message_id=$($donePayload.message_id)"

$semanticsOk = $true
foreach ($needle in $AnswerMustInclude) {
    if ($answerText -notlike "*$needle*") {
        $semanticsOk = $false
        Write-Host "  missing required answer semantic: $needle" -ForegroundColor Red
    }
}
if ($semanticsOk) {
    Write-Layer "ANSWER_SEMANTICS_OK" "PASS" "includes: $($AnswerMustInclude -join ', ')"
}
else {
    $previewLen = [Math]::Min(160, $answerText.Length)
    $preview = ""
    if ($previewLen -gt 0) { $preview = $answerText.Substring(0, $previewLen) }
    Write-Layer "ANSWER_SEMANTICS_OK" "FAIL" "answer preview: $preview"
    Fail-Demo "supported answer missing required semantics"
}

if ($citations.Count -lt 1) {
    Write-Layer "CITATION_PRESENT" "FAIL"
    Fail-Demo "supported done event has empty citations after $maxChatAttempts attempts"
}
Write-Layer "CITATION_PRESENT" "PASS" "count=$($citations.Count)"

$sourceOk = $false
$citeDetail = ""
foreach ($c in $citations) {
    $nameOk = ($c.doc_name -like "*$CitationMustMatchDocName*")
    $idOk = ($c.document_id -eq $leaveDocId)
    if (($nameOk -or $idOk) -and $c.excerpt) {
        $sourceOk = $true
        $citeDetail = "doc_name=$($c.doc_name) document_id=$($c.document_id)"
        try {
            $resolved = Invoke-RestMethod `
                -Uri "$BaseUrl/api/v1/knowledge-bases/$kbId/citations/resolve?document_id=$($c.document_id)&chunk_id=$($c.chunk_id)" `
                -Headers $authHeader
            if ($resolved) {
                $citeDetail += " resolve=ok"
            }
        }
        catch {
            $citeDetail += " resolve=skip"
        }
        break
    }
}
if (-not $sourceOk) {
    $names = ($citations | ForEach-Object { $_.doc_name }) -join ", "
    Write-Layer "CITATION_SOURCE_OK" "FAIL" "citations pointed to: $names"
    Fail-Demo "citation did not reference canonical leave-policy corpus document"
}
Write-Layer "CITATION_SOURCE_OK" "PASS" $citeDetail

if ($SkipUnsupported) {
    Write-Layer "UNSUPPORTED_CASE_OK" "SKIP" "SkipUnsupported set"
}
else {
    Write-Step ("unsupported question: " + $UnsupportedQuestion)
    try {
        $sseU = Invoke-ChatSse -KbId $kbId -Token $token -Message $UnsupportedQuestion
    }
    catch {
        Write-Layer "UNSUPPORTED_CASE_OK" "FAIL" "$($_.Exception.Message)"
        Fail-Demo "unsupported chat failed"
    }
    $donesU = @(Get-SseEventPayloads $sseU "done")
    if ($donesU.Count -lt 1) {
        Write-Layer "UNSUPPORTED_CASE_OK" "FAIL" "missing done"
        Fail-Demo "unsupported chat missing done event"
    }
    $answerU = Get-SseAnswerText $sseU
    $citesU = @()
    if ($null -ne $donesU[-1].citations) { $citesU = @($donesU[-1].citations) }
    $refused = ($answerU -like "*$RefuseMarker*")
    if ($refused) {
        Write-Layer "UNSUPPORTED_CASE_OK" "PASS" "REFUSE (citations=$($citesU.Count))"
    }
    else {
        $previewLen = [Math]::Min(120, $answerU.Length)
        $preview = ""
        if ($previewLen -gt 0) { $preview = $answerU.Substring(0, $previewLen) }
        Write-Layer "UNSUPPORTED_CASE_OK" "FAIL" "answer did not refuse; preview=$preview"
        Fail-Demo "unsupported case did not show refuse semantics"
    }
}

if ($SkipCleanup) {
    Write-Host "[demo] cleanup skipped - retained kb_id=$kbId user=$email" -ForegroundColor DarkYellow
}
else {
    Write-Step "cleanup: delete demo knowledge base"
    try {
        Invoke-RestMethod -Method Delete `
            -Uri "$BaseUrl/api/v1/knowledge-bases/$kbId" `
            -Headers $authHeader | Out-Null
        Write-Host "[demo] deleted kb_id=$kbId (demo user account retained: $email)" -ForegroundColor DarkGray
    }
    catch {
        Write-Host "[demo] cleanup warning: could not delete KB - $($_.ErrorDetails.Message)" -ForegroundColor DarkYellow
    }
}

Write-Host ""
Write-Host "===== Canonical Demo layer summary =====" -ForegroundColor Green
foreach ($k in $script:Results.Keys) {
    Write-Host ("  {0} = {1}" -f $k, $script:Results[$k])
}
Write-Host ""
Write-Host "PROVES     : public product path runnable; ingest/index; bounded grounded Q; citation/provenance on demo corpus" -ForegroundColor Green
Write-Host "DOES NOT   : general RAG accuracy; Agent/Critic/L3/L4; model superiority; production load" -ForegroundColor DarkGray
Write-Host "V1_0_C4_CANONICAL_DEMO_PASS" -ForegroundColor Green
exit 0
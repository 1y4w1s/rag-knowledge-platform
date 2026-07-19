$email = "ent-" + ([guid]::NewGuid().ToString().Substring(0,8)) + "@e.com"
$pw = "JudgePass123!"
$api = "http://localhost:8000"

# Register & login
$null = curl.exe -s -X POST "$api/api/v1/auth/register" -H "Content-Type: application/json" -d "{`"email`":`"$email`",`"username`":`"ent$([guid]::NewGuid().ToString().Substring(0,6))`",`"password`":`"$pw`",`"account_type`":`"personal`"}"
$log = curl.exe -s -X POST "$api/api/v1/auth/login" -H "Content-Type: application/json" -d "{`"identifier`":`"$email`",`"password`":`"$pw`"}"
$tok = ($log | ConvertFrom-Json).access_token
Write-Output "TOKEN_OK"

# Create KB
$kb = curl.exe -s -X POST "$api/api/v1/knowledge-bases?workspace=personal" -H "Authorization: Bearer $tok" -H "Content-Type: application/json" -d '{"name":"Enterprise-QA"}'
$kbId = ($kb | ConvertFrom-Json).id
Write-Output "KB_ID=$kbId"

# Upload docs via HTTP API (uses main process, not sub-process)
Get-ChildItem "backend/tests/fixtures/acme_*.md" | ForEach-Object {
    Write-Output "Uploading $($_.Name)..."
    $resp = curl.exe -s -X POST "$api/api/v1/knowledge-bases/$kbId/documents?workspace=personal" -H "Authorization: Bearer $tok" -F "files=@$($_.FullName)"
}
Write-Output "UPLOAD_DONE"

# Wait for ingestion
for ($i=0; $i -lt 120; $i++) {
    $docs = curl.exe -s "$api/api/v1/knowledge-bases/$kbId/documents?workspace=personal&per_page=20" -H "Authorization: Bearer $tok"
    $items = ($docs | ConvertFrom-Json).items
    $pending = ($items | Where-Object { $_.status -ne "completed" }).Count
    if ($items.Count -ge 6 -and $pending -eq 0) {
        Write-Output "ALL_COMPLETED ($($items.Count) docs)"
        break
    }
    Write-Output "  waiting... ($pending pending)"
    Start-Sleep -Seconds 5
}

# Save kb_id
Set-Content -Path "backend/tests/fixtures/.ent_kb_id" -Value $kbId
Write-Output "SAVED kb_id=$kbId"

$email = "ent-" + ([guid]::NewGuid().ToString().Substring(0,8)) + "@e.com"
$pw = "JudgePass123!"

# Register & login
$reg = curl.exe -s -X POST http://localhost:8000/api/v1/auth/register -H "Content-Type: application/json" -d "{`"email`":`"$email`",`"username`":`"ent$([guid]::NewGuid().ToString().Substring(0,8))`",`"password`":`"$pw`",`"account_type`":`"personal`"}"
$log = curl.exe -s -X POST http://localhost:8000/api/v1/auth/login -H "Content-Type: application/json" -d "{`"identifier`":`"$email`",`"password`":`"$pw`"}"

# Parse token
$logJson = $log | ConvertFrom-Json
$tok = $logJson.access_token
Write-Output "TOKEN_OK"

# Create KB
$kb = curl.exe -s -X POST "http://localhost:8000/api/v1/knowledge-bases?workspace=personal" -H "Authorization: Bearer $tok" -H "Content-Type: application/json" -d '{"name":"Enterprise-QA"}'
$kbJson = $kb | ConvertFrom-Json
$kbId = $kbJson.id
Write-Output "KB_ID=$kbId"

# Upload each doc
Get-ChildItem "backend/tests/fixtures/acme_*.md" | ForEach-Object {
    Write-Output "Uploading $($_.Name)..."
    $resp = curl.exe -s -X POST "http://localhost:8000/api/v1/knowledge-bases/$kbId/documents?workspace=personal" -H "Authorization: Bearer $tok" -F "files=@$($_.FullName)"
    Write-Output "  $($resp | ConvertFrom-Json | ConvertTo-Json -Compress)"
}

# Wait for completion
for ($i=0; $i -lt 60; $i++) {
    $docs = curl.exe -s "http://localhost:8000/api/v1/knowledge-bases/$kbId/documents?workspace=personal&per_page=10" -H "Authorization: Bearer $tok"
    $items = ($docs | ConvertFrom-Json).items
    if ($items -and ($items | Where-Object { $_.status -ne "completed" }).Count -eq 0) {
        Write-Output "ALL_COMPLETED: $($items.Count) docs"
        break
    }
    Start-Sleep -Seconds 3
}

# Save kb_id for next step
Set-Content -Path "backend/tests/fixtures/.ent_kb_id" -Value $kbId
Write-Output "SAVED_OK"

Set-Location $PSScriptRoot

$headers = @{}
if ($env:ARBITRAGE_API_KEY) {
    $headers["X-API-Key"] = $env:ARBITRAGE_API_KEY
}

Write-Host ""
Write-Host "Running CLI route smoke test..."
py main.py "test message"
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "Running dashboard smoke test..."
py dashboard.py
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "Checking API health endpoint..."
try {
    Invoke-RestMethod -Uri "http://127.0.0.1:8095/health" -Method Get | ConvertTo-Json -Depth 8
}
catch {
    Write-Error "API health check failed. Start the API with .\start_api.ps1, then rerun .\smoke_test.ps1."
    exit 1
}

Write-Host ""
Write-Host "Checking API providers endpoint..."
try {
    Invoke-RestMethod -Uri "http://127.0.0.1:8095/providers" -Method Get -Headers $headers | ConvertTo-Json -Depth 8
}
catch {
    Write-Error "API providers check failed. Start the API with .\start_api.ps1, then rerun .\smoke_test.ps1."
    exit 1
}

$ErrorActionPreference = "Stop"

$baseUrl = $env:ARBITRAGE_BASE_URL

if (-not $baseUrl) {
    $baseUrl = "http://127.0.0.1:8095"
}

$headers = @{}

if ($env:ARBITRAGE_API_KEY) {
    $headers["X-API-Key"] = $env:ARBITRAGE_API_KEY
}

Invoke-RestMethod `
    -Uri "$baseUrl/system/checkpoint" `
    -Method Post `
    -Headers $headers |
    ConvertTo-Json -Depth 10

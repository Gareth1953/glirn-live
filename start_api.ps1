Set-Location $PSScriptRoot

Write-Host ""
Write-Host "Starting ArbitrageEngineV1 API on http://127.0.0.1:8095"
Write-Host "Press CTRL + C to stop."
Write-Host ""

py -m uvicorn app:app --host 127.0.0.1 --port 8095

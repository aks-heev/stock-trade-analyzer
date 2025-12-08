# PowerShell script to test Render API
# Usage: .\test_render_api.ps1

$API_URL = "https://stock-trade-analyzer-k7k4.onrender.com"

Write-Host "Testing Render API..." -ForegroundColor Cyan
Write-Host "URL: $API_URL" -ForegroundColor Yellow
Write-Host ""

# Test 1: Health Check
Write-Host "1. Testing /health endpoint..." -ForegroundColor Green
try {
    $response = Invoke-WebRequest -Uri "$API_URL/health" -Method GET -UseBasicParsing
    Write-Host "   Status: $($response.StatusCode)" -ForegroundColor Green
    Write-Host "   Response: $($response.Content)" -ForegroundColor White
} catch {
    Write-Host "   Error: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "   Status Code: $($_.Exception.Response.StatusCode.value__)" -ForegroundColor Red
}

Write-Host ""

# Test 2: Root endpoint
Write-Host "2. Testing / endpoint..." -ForegroundColor Green
try {
    $response = Invoke-WebRequest -Uri "$API_URL/" -Method GET -UseBasicParsing
    Write-Host "   Status: $($response.StatusCode)" -ForegroundColor Green
    Write-Host "   Response: $($response.Content)" -ForegroundColor White
} catch {
    Write-Host "   Error: $($_.Exception.Message)" -ForegroundColor Red
    if ($_.Exception.Response) {
        Write-Host "   Status Code: $($_.Exception.Response.StatusCode.value__)" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "Test complete!" -ForegroundColor Cyan


param(
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 3000,
    [int]$OpenMAICPort = 3001,
    [string]$HostAddress = "127.0.0.1",
    [switch]$SkipMigration,
    [switch]$SkipWorker,
    [switch]$SkipFrontend,
    [switch]$SkipOpenMAIC,
    [switch]$AllowExistingWorker
)

$ErrorActionPreference = "Stop"
$DemoScript = Join-Path $PSScriptRoot "start_phase31_demo.ps1"
if (-not (Test-Path $DemoScript)) {
    throw "Missing demo launcher: $DemoScript"
}

Write-Host "Starting local dev stack (backend + arq worker + frontend)..." -ForegroundColor Cyan
Write-Host "Logs: runtime-logs/" -ForegroundColor DarkGray

& $DemoScript `
    -BackendPort $BackendPort `
    -FrontendPort $FrontendPort `
    -OpenMAICPort $OpenMAICPort `
    -HostAddress $HostAddress `
    -SkipMigration:$SkipMigration `
    -SkipWorker:$SkipWorker `
    -SkipFrontend:$SkipFrontend `
    -SkipOpenMAIC:$SkipOpenMAIC `
    -AllowExistingWorker:$AllowExistingWorker

Write-Host ""
Write-Host "Harness smoke:" -ForegroundColor Cyan
Write-Host "python scripts/agent_demo_check.py --base-url http://$HostAddress`:$BackendPort/api/v1"
Write-Host "cd backend; python -m pytest tests/test_agent_harness.py tests/test_multimodal_review.py -q"
Write-Host "cd backend; python scripts/agent_multimodal_harness.py"

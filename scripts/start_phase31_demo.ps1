param(
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 3000,
    [string]$HostAddress = "127.0.0.1",
    [switch]$SkipMigration,
    [switch]$SkipWorker,
    [switch]$SkipFrontend,
    [switch]$AllowExistingWorker
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$LogDir = Join-Path $Root "runtime-logs"
$ApiBaseUrl = "http://$HostAddress`:$BackendPort/api/v1"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Assert-PortFree {
    param([int]$Port, [string]$Name)
    $existing = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue |
        Where-Object { $_.State -eq "Listen" } |
        Select-Object -First 1
    if ($existing) {
        throw "$Name port $Port is already used by PID $($existing.OwningProcess). Stop the old service or choose another port."
    }
}

function Start-DemoProcess {
    param(
        [string]$Name,
        [string]$WorkingDirectory,
        [string]$Command,
        [string]$LogName
    )
    $stdout = Join-Path $LogDir "$LogName.out.log"
    $stderr = Join-Path $LogDir "$LogName.err.log"
    $process = Start-Process `
        -FilePath "powershell.exe" `
        -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", "Set-Location '$WorkingDirectory'; $Command") `
        -WindowStyle Hidden `
        -RedirectStandardOutput $stdout `
        -RedirectStandardError $stderr `
        -PassThru
    Write-Host "$Name started: PID $($process.Id), logs $stdout / $stderr" -ForegroundColor Green
}

function Get-AgentWorkerProcesses {
    Get-CimInstance Win32_Process |
        Where-Object {
            $_.CommandLine -like "*arq app.workers.agent_worker.WorkerSettings*"
        } |
        Select-Object ProcessId,CommandLine
}

Assert-PortFree -Port $BackendPort -Name "Backend"
if (-not $SkipFrontend) {
    Assert-PortFree -Port $FrontendPort -Name "Frontend"
}
if (-not $SkipWorker -and -not $AllowExistingWorker) {
    $workers = @(Get-AgentWorkerProcesses)
    if ($workers.Count -gt 0) {
        $workerList = ($workers | ForEach-Object { "PID $($_.ProcessId): $($_.CommandLine)" }) -join "`n"
        throw "Existing Agent Worker processes were detected. Stop them first to prevent stale workers from consuming Redis queue jobs, or pass -AllowExistingWorker only when they are known to be current.`n$workerList"
    }
}

if (-not $SkipMigration) {
    Write-Host "Running database migrations..." -ForegroundColor Cyan
    Push-Location (Join-Path $Root "backend")
    python -m alembic upgrade head
    Pop-Location
}

Start-DemoProcess `
    -Name "FastAPI Backend" `
    -WorkingDirectory (Join-Path $Root "backend") `
    -Command "python -m uvicorn app.main:app --host $HostAddress --port $BackendPort --reload" `
    -LogName "phase31-backend"

if (-not $SkipWorker) {
    Start-DemoProcess `
        -Name "arq Agent Worker" `
        -WorkingDirectory (Join-Path $Root "backend") `
        -Command "python -m arq app.workers.agent_worker.WorkerSettings" `
        -LogName "phase31-worker"
}

if (-not $SkipFrontend) {
    Start-DemoProcess `
        -Name "Next.js Frontend" `
        -WorkingDirectory (Join-Path $Root "frontend") `
        -Command "`$env:NEXT_PUBLIC_API_BASE_URL='$ApiBaseUrl'; npm run dev -- --hostname $HostAddress --port $FrontendPort" `
        -LogName "phase31-frontend"
}

$encodedApiBase = [System.Uri]::EscapeDataString($ApiBaseUrl)
Write-Host ""
Write-Host "Phase 3.1 demo entry:" -ForegroundColor Cyan
Write-Host "http://$HostAddress`:$FrontendPort/assistant?api_base=$encodedApiBase"
Write-Host ""
Write-Host "Stable smoke check:" -ForegroundColor Cyan
Write-Host "python scripts/agent_demo_check.py --base-url $ApiBaseUrl"

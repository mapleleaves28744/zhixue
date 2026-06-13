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
$Root = Split-Path -Parent $PSScriptRoot
$LogDir = Join-Path $Root "runtime-logs"
$ApiBaseUrl = "http://$HostAddress`:$BackendPort/api/v1"
$OpenMAICBaseUrl = "http://$HostAddress`:$OpenMAICPort"
$RootEnvPath = Join-Path $Root ".env"

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

function Get-RootEnvValue {
    param([string]$Name)
    if (-not (Test-Path $RootEnvPath)) {
        return ""
    }
    $line = Get-Content $RootEnvPath |
        Where-Object { $_ -match "^\s*$([regex]::Escape($Name))=" } |
        Select-Object -Last 1
    if (-not $line) {
        return ""
    }
    $value = ($line -split "=", 2)[1].Trim()
    if (($value.StartsWith('"') -and $value.EndsWith('"')) -or
        ($value.StartsWith("'") -and $value.EndsWith("'"))) {
        return $value.Substring(1, $value.Length - 2)
    }
    return $value
}

function New-RandomSecret {
    $bytes = New-Object byte[] 32
    $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $rng.GetBytes($bytes)
    } finally {
        $rng.Dispose()
    }
    return ([BitConverter]::ToString($bytes).Replace("-", "")).ToLowerInvariant()
}

function Set-RootEnvValue {
    param(
        [string]$Name,
        [string]$Value
    )
    if (-not (Test-Path $RootEnvPath)) {
        New-Item -ItemType File -Path $RootEnvPath -Force | Out-Null
    }
    $lines = @(Get-Content $RootEnvPath -ErrorAction SilentlyContinue)
    $pattern = "^\s*$([regex]::Escape($Name))="
    $updated = $false
    for ($i = 0; $i -lt $lines.Count; $i += 1) {
        if ($lines[$i] -match $pattern) {
            $lines[$i] = "$Name=$Value"
            $updated = $true
            break
        }
    }
    if (-not $updated) {
        if ($lines.Count -gt 0 -and $lines[-1].Trim().Length -gt 0) {
            $lines += ""
        }
        $lines += "$Name=$Value"
    }
    Set-Content -Path $RootEnvPath -Value $lines -Encoding UTF8
}

function Sync-OpenMAICTokensToEnvFile {
    param(
        [string]$InternalToken,
        [string]$SigningSecret
    )
    Set-RootEnvValue "OPENMAIC_ENABLED" "true"
    Set-RootEnvValue "OPENMAIC_BASE_URL" $OpenMAICBaseUrl
    Set-RootEnvValue "OPENMAIC_PUBLIC_BASE_URL" $OpenMAICBaseUrl
    Set-RootEnvValue "OPENMAIC_INTERNAL_TOKEN" $InternalToken
    Set-RootEnvValue "OPENMAIC_SIGNING_SECRET" $SigningSecret

    $openmaicEnvPath = Join-Path $Root "third_party\openmaic\.env.local"
    @(
        "OPENMAIC_INTERNAL_TOKEN=$InternalToken"
        "OPENMAIC_SIGNING_SECRET=$SigningSecret"
    ) | Set-Content -Path $openmaicEnvPath -Encoding UTF8
}

function Configure-OpenMAICEnvironment {
    $internalToken = Get-RootEnvValue "OPENMAIC_INTERNAL_TOKEN"
    $signingSecret = Get-RootEnvValue "OPENMAIC_SIGNING_SECRET"
    if (-not $internalToken) {
        $internalToken = New-RandomSecret
    }
    if (-not $signingSecret) {
        $signingSecret = New-RandomSecret
    }

    $env:OPENMAIC_ENABLED = "true"
    $env:OPENMAIC_BASE_URL = $OpenMAICBaseUrl
    $env:OPENMAIC_PUBLIC_BASE_URL = $OpenMAICBaseUrl
    $env:OPENMAIC_INTERNAL_TOKEN = $internalToken
    $env:OPENMAIC_SIGNING_SECRET = $signingSecret
    Sync-OpenMAICTokensToEnvFile -InternalToken $internalToken -SigningSecret $signingSecret

    $llmApiKey = Get-RootEnvValue "LLM_API_KEY"
    $llmBaseUrl = Get-RootEnvValue "LLM_BASE_URL"
    $llmModel = Get-RootEnvValue "LLM_MODEL_NAME"
    if ($llmApiKey) {
        $env:XIAOMI_API_KEY = $llmApiKey
        $env:TTS_XIAOMI_MIMO_API_KEY = $llmApiKey
        $env:ASR_XIAOMI_MIMO_API_KEY = $llmApiKey
    }
    if ($llmBaseUrl) {
        $env:XIAOMI_BASE_URL = $llmBaseUrl
        $env:TTS_XIAOMI_MIMO_BASE_URL = $llmBaseUrl
        $env:ASR_XIAOMI_MIMO_BASE_URL = $llmBaseUrl
    }
    if ($llmModel) {
        $env:XIAOMI_MODELS = $llmModel
        $env:DEFAULT_MODEL = "xiaomi:$llmModel"
    }

    $debugValue = Get-RootEnvValue "DEBUG"
    if ($debugValue -match "^(?i:true|false|1|0|yes|no|on|off)$") {
        $env:DEBUG = $debugValue
    } elseif ($debugValue) {
        Write-Host "Root .env DEBUG value is not boolean; using DEBUG=false for this launch." -ForegroundColor Yellow
        $env:DEBUG = "false"
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
if (-not $SkipOpenMAIC) {
    Assert-PortFree -Port $OpenMAICPort -Name "OpenMAIC"
    Configure-OpenMAICEnvironment
}
if (-not $SkipWorker -and -not $AllowExistingWorker) {
    $workers = @(Get-AgentWorkerProcesses)
    if ($workers.Count -gt 0) {
        $workerList = ($workers | ForEach-Object { "PID $($_.ProcessId): $($_.CommandLine)" }) -join "`n"
        throw "Existing Agent Worker processes were detected. Stop them first to prevent stale workers from consuming Redis queue jobs, or pass -AllowExistingWorker only when they are known to be current.`n$workerList"
    }
}

if (-not $SkipOpenMAIC) {
    Start-DemoProcess `
        -Name "OpenMAIC Classroom Engine" `
        -WorkingDirectory (Join-Path $Root "third_party\openmaic") `
        -Command "pnpm exec next dev --hostname $HostAddress --port $OpenMAICPort" `
        -LogName "phase31-openmaic"
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
    -Command "python -m uvicorn app.main:app --host $HostAddress --port $BackendPort" `
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
if (-not $SkipOpenMAIC) {
    Write-Host "OpenMAIC engine: $OpenMAICBaseUrl"
}
Write-Host ""
Write-Host "Stable smoke check:" -ForegroundColor Cyan
Write-Host "python scripts/agent_demo_check.py --base-url $ApiBaseUrl"

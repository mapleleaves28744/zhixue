param(
    [switch]$Backend,
    [switch]$Frontend,
    [switch]$OpenMAIC,
    [switch]$Database,
    [switch]$MainChain,
    [string]$MainChainBaseUrl = "http://127.0.0.1:8000/api/v1",
    [switch]$AgentDemo,
    [string]$AgentDemoBaseUrl = "http://127.0.0.1:8000/api/v1",
    [switch]$All
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot

if (-not ($Backend -or $Frontend -or $OpenMAIC -or $Database -or $MainChain -or $AgentDemo -or $All)) {
    $All = $true
}

function Run-Step {
    param(
        [string]$Name,
        [scriptblock]$Command
    )
    Write-Host "`n==> $Name" -ForegroundColor Cyan
    & $Command
    Write-Host "OK: $Name" -ForegroundColor Green
}

if ($All -or $Database) {
    Run-Step "Alembic migration" {
        Push-Location "$Root\backend"
        python -m alembic upgrade head
        Pop-Location
    }
}

if ($All -or $Backend) {
    Run-Step "Backend pytest" {
        Push-Location "$Root\backend"
        python -m pytest
        Pop-Location
    }

    Run-Step "FastAPI import check" {
        Push-Location "$Root\backend"
        python -c "from app.main import app; print(app.title)"
        Pop-Location
    }
}

if ($All -or $Frontend) {
    Run-Step "Frontend typecheck" {
        Push-Location "$Root\frontend"
        npm run typecheck
        Pop-Location
    }

    Run-Step "Frontend build" {
        Push-Location "$Root\frontend"
        npm run build
        Pop-Location
    }
}

if ($OpenMAIC) {
    Run-Step "OpenMAIC internal auth test" {
        Push-Location "$Root\third_party\openmaic"
        pnpm vitest run tests/server/internal-auth.test.ts
        Pop-Location
    }

    Run-Step "OpenMAIC production build" {
        Push-Location "$Root\third_party\openmaic"
        pnpm build
        Pop-Location
    }
}

if ($MainChain) {
    Run-Step "Real LLM main chain acceptance" {
        Push-Location $Root
        python scripts/main_chain_check.py --base-url $MainChainBaseUrl
        Pop-Location
    }
}

if ($AgentDemo) {
    Run-Step "Phase 3.1 Agent demo acceptance" {
        Push-Location $Root
        python scripts/agent_demo_check.py --base-url $AgentDemoBaseUrl
        Pop-Location
    }
}

Write-Host "`nLocal checks completed." -ForegroundColor Green

param(
    [int]$ApiPort = 8000,
    [int]$DashboardPort = 8501
)

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$LogDir = Join-Path $RepoRoot ".local\runtime_logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Test-PortFree {
    param([int]$Port)
    $connection = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue
    if ($connection) {
        Write-Host "Port $Port is already in use. Inspect before stopping anything:"
        Write-Host "Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue | Select-Object LocalAddress,LocalPort,State,OwningProcess"
        return $false
    }
    return $true
}

$apiFree = Test-PortFree -Port $ApiPort
$dashboardFree = Test-PortFree -Port $DashboardPort
if (-not ($apiFree -and $dashboardFree)) {
    Write-Host "Runtime demo was not started because an expected port is occupied."
    exit 1
}

$apiCommand = "Set-Location '$RepoRoot'; python -m uvicorn app.main:app --host 127.0.0.1 --port $ApiPort *> '$LogDir\fastapi.log'"
$dashboardCommand = "Set-Location '$RepoRoot'; python -m streamlit run dashboard/streamlit_app.py --server.port $DashboardPort *> '$LogDir\streamlit.log'"

Start-Process powershell -WindowStyle Hidden -ArgumentList "-NoExit", "-Command", $apiCommand
Start-Process powershell -WindowStyle Hidden -ArgumentList "-NoExit", "-Command", $dashboardCommand

Write-Host "Runtime demo start requested."
Write-Host "FastAPI:   http://127.0.0.1:$ApiPort/health"
Write-Host "Streamlit: http://127.0.0.1:$DashboardPort"
Write-Host "Logs:      $LogDir"
Write-Host "Stop manually by closing the spawned PowerShell processes or pressing Ctrl+C if you started the commands yourself."

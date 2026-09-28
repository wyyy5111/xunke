$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$BackendPort = if ($env:BACKEND_PORT) { $env:BACKEND_PORT } else { "8000" }
$FrontendPort = if ($env:FRONTEND_PORT) { $env:FRONTEND_PORT } else { "5173" }

if ($BackendPort -eq $FrontendPort) {
    throw "BACKEND_PORT and FRONTEND_PORT must be different."
}

function Assert-PortFree([string]$Port) {
    $listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if ($listener) { throw "Port $Port is already in use. Set BACKEND_PORT or FRONTEND_PORT and retry." }
}

Assert-PortFree $BackendPort
Assert-PortFree $FrontendPort

if (-not (Test-Path "$Root\.env")) {
    Copy-Item "$Root\.env.example" "$Root\.env"
}

if (-not (Get-Command node -ErrorAction SilentlyContinue) -or -not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw "Node.js/npm was not found. Install Node.js 24.x first."
}
& node -e 'const [m,n]=process.versions.node.split(".").map(Number); process.exit((m===20&&n>=19)||(m===22&&n>=12)||m>=24?0:1)'
if ($LASTEXITCODE -ne 0) { throw "Install Node.js 24.x (or 20.19+/22.12+) for Vite 8." }

$Python = Get-Command py -ErrorAction SilentlyContinue
if (-not $Python) { throw "Python Launcher (py) was not found. Install Python 3.12 first." }

if (-not (Test-Path "$Root\.venv\Scripts\python.exe")) {
    & py -3.12 -m venv "$Root\.venv"
    if ($LASTEXITCODE -ne 0) { throw "Failed to create Python 3.12 environment." }
}

& "$Root\.venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r "$Root\backend\requirements.txt"
if ($LASTEXITCODE -ne 0) { throw "Python dependency installation failed." }
Push-Location "$Root\frontend"
try {
    npm ci --no-audit --no-fund
    if ($LASTEXITCODE -ne 0) { throw "npm dependency installation failed." }
} finally { Pop-Location }

$backendArgs = "-NoExit", "-Command", "Set-Location '$Root'; `$env:PYTHONPATH='$Root\backend'; & '$Root\.venv\Scripts\python.exe' -m uvicorn app.main:app --host 127.0.0.1 --port $BackendPort"
$frontendArgs = "-NoExit", "-Command", "Set-Location '$Root\frontend'; `$env:BACKEND_PORT='$BackendPort'; `$env:FRONTEND_PORT='$FrontendPort'; `$env:VITE_DEV_PROXY_TARGET='http://127.0.0.1:$BackendPort'; npm run dev -- --host 127.0.0.1 --port $FrontendPort"

Start-Process powershell -ArgumentList $backendArgs
Start-Process powershell -ArgumentList $frontendArgs
Start-Sleep -Seconds 3
Start-Process "http://127.0.0.1:$FrontendPort"

Write-Host "XunkeFlow started. Backend: $BackendPort, Frontend: $FrontendPort"

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root
if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env" }
docker compose up --build -d
docker compose ps
Start-Process "http://127.0.0.1:5173"

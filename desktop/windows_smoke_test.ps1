param(
    [string]$InstallerPath = "",
    [string]$OutputPath = ""
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
if (-not $InstallerPath) {
    $InstallerPath = Get-ChildItem -LiteralPath (Join-Path $PSScriptRoot "dist") `
        -Filter "XunkeFlow_Windows_*_Setup.exe" | Sort-Object LastWriteTime -Descending | `
        Select-Object -First 1 -ExpandProperty FullName
}
if (-not $InstallerPath -or -not (Test-Path -LiteralPath $InstallerPath)) {
    throw "Windows installer not found."
}

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$work = Join-Path $env:TEMP "xunkeflow-desktop-smoke-$stamp"
$installRoot = Join-Path $work "app"
$userRoot = Join-Path $work "user-data"
$logPath = if ($OutputPath) { $OutputPath } else { Join-Path $work "windows-smoke.log" }
New-Item -ItemType Directory -Force -Path $work, $installRoot, $userRoot | Out-Null

function Write-Result([string]$Message) {
    $line = "$(Get-Date -Format o) $Message"
    $line | Tee-Object -FilePath $logPath -Append
}

function Invoke-Login([string]$Username) {
    $payload = @{ username = $Username; password = "123456" } | ConvertTo-Json
    $response = Invoke-RestMethod -Method Post -Uri "$script:baseUrl/api/auth/login" `
        -ContentType "application/json" -Body $payload -TimeoutSec 15
    if ($response.code -ne 0 -or $response.data.user.username -ne $Username) {
        throw "Login verification failed for $Username"
    }
    Write-Result "LOGIN_OK user=$Username role=$($response.data.role)"
}

try {
    Write-Result "INSTALL_START installer=$InstallerPath"
    $installer = Start-Process -FilePath $InstallerPath -ArgumentList "/S", "/D=$installRoot" -Wait -PassThru
    if ($installer.ExitCode -ne 0) { throw "Installer exit code: $($installer.ExitCode)" }

    $appExe = Join-Path $installRoot "循课 XunkeFlow.exe"
    $pythonExe = Join-Path $installRoot "resources\backend-windows\pythonw.exe"
    $frontendIndex = Join-Path $installRoot "resources\frontend_dist\index.html"
    foreach ($required in @($appExe, $pythonExe, $frontendIndex)) {
        if (-not (Test-Path -LiteralPath $required)) { throw "Missing installed file: $required" }
    }
    Write-Result "INSTALL_OK"

    $appProcess = Start-Process -FilePath $appExe -ArgumentList "--user-data-dir=$userRoot" -PassThru
    $script:baseUrl = $null
    foreach ($port in 8173..8232) {
        if ($script:baseUrl) { break }
        try {
            $health = Invoke-RestMethod -Uri "http://127.0.0.1:$port/api/health" -TimeoutSec 1
            if ($health.status -eq "ok" -and $health.app -eq "XunkeFlow") {
                $script:baseUrl = "http://127.0.0.1:$port"
            }
        } catch { }
    }
    for ($attempt = 0; -not $script:baseUrl -and $attempt -lt 120; $attempt++) {
        Start-Sleep -Milliseconds 500
        foreach ($port in 8173..8232) {
            try {
                $health = Invoke-RestMethod -Uri "http://127.0.0.1:$port/api/health" -TimeoutSec 1
                if ($health.status -eq "ok" -and $health.app -eq "XunkeFlow") {
                    $script:baseUrl = "http://127.0.0.1:$port"
                    break
                }
            } catch { }
        }
    }
    if (-not $script:baseUrl) { throw "Desktop service did not become healthy." }
    Write-Result "HEALTH_OK url=$script:baseUrl"

    $loginPage = Invoke-WebRequest -UseBasicParsing -Uri "$script:baseUrl/login" -TimeoutSec 15
    if ($loginPage.StatusCode -ne 200) { throw "Login page returned $($loginPage.StatusCode)" }
    Invoke-Login "admin"
    Invoke-Login "teacher"
    Invoke-Login "student01"

    $database = Join-Path $userRoot "data\xunkeflow.db"
    if (-not (Test-Path -LiteralPath $database) -or (Get-Item $database).Length -lt 4096) {
        throw "Desktop database was not initialized."
    }
    Write-Result "DATABASE_OK bytes=$((Get-Item $database).Length)"

    $null = $appProcess.CloseMainWindow()
    if (-not $appProcess.WaitForExit(15000)) {
        Stop-Process -Id $appProcess.Id -Force
    }
    Start-Sleep -Seconds 2
    $stillHealthy = $false
    try {
        Invoke-RestMethod -Uri "$script:baseUrl/api/health" -TimeoutSec 2 | Out-Null
        $stillHealthy = $true
    } catch { }
    if ($stillHealthy) { throw "Backend process remained after application exit." }
    Write-Result "PROCESS_CLEANUP_OK"
    Write-Result "WINDOWS_SMOKE_SUCCESS"
} finally {
    if ($appProcess -and -not $appProcess.HasExited) {
        Stop-Process -Id $appProcess.Id -Force -ErrorAction SilentlyContinue
    }
}

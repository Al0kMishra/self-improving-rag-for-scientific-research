$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent $ScriptDir
Set-Location $RootDir

$BackendPort = if ($env:BACKEND_PORT) { $env:BACKEND_PORT } else { "8000" }

$backendProcess = Start-Process -FilePath "$RootDir\.venv\Scripts\uvicorn.exe" -ArgumentList "app.main:app --app-dir backend --reload --port $BackendPort" -PassThru

try {
    Set-Location "$RootDir\frontend"
    npm.cmd run dev
} finally {
    if ($backendProcess -and -not $backendProcess.HasExited) {
        Stop-Process -Id $backendProcess.Id -Force
    }
}

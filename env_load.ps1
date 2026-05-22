# Activate the Python virtual environment for this project (PowerShell)
# Usage: . .\env_load.ps1

$venvPath = Join-Path $PSScriptRoot 'venv\Scripts\Activate.ps1'
if (Test-Path $venvPath) {
    . $venvPath
    Write-Host '[INFO] Virtual environment activated.'
} else {
    Write-Host "[ERROR] No virtual environment found. Run " -NoNewline
    Write-Host "python -m venv venv" -ForegroundColor Yellow -NoNewline
    Write-Host " first."
}

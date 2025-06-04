# Activate the Python virtual environment for this project (PowerShell)
# Usage: . .\env_load.ps1

$venvPath = Join-Path $PSScriptRoot 'venv\Scripts\Activate.ps1'
if (Test-Path $venvPath) {
    . $venvPath
    Write-Host '[INFO] Virtual environment activated.'
} else {
    Write-Host '[ERROR] No virtual environment found. Run `u001b[33mpython -m venv venv`u001b[0m first.'
}

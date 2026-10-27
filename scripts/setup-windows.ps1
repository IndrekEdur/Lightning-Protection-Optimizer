param([string]$PythonVersion = '3.11')
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
py "-$PythonVersion" -m venv .venv
if ($LASTEXITCODE -ne 0) { throw 'Install a supported 64-bit Python (3.11/3.12/3.13) with the Windows launcher; specify -PythonVersion if needed.' }
& .\.venv\Scripts\python.exe -m pip install -r requirements-ifc.txt
if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed.' }
New-Item -ItemType Directory -Force test_models | Out-Null
Push-Location frontend
try {
    npm ci
    if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed. Check Node version (20.19+ or 22.12+).' }
} finally { Pop-Location }
Write-Host 'Setup complete. Run scripts\start-backend.ps1 and scripts\start-frontend.ps1 in separate terminals.'

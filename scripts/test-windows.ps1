$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$env:PYTHONPATH = Join-Path (Get-Location) 'backend'
& .\.venv\Scripts\python.exe -m pytest backend/tests -q
if ($LASTEXITCODE -ne 0) { throw 'Backend tests failed.' }
Push-Location frontend
try {
    npm run build
    if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
} finally { Pop-Location }

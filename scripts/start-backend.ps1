$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$env:PYTHONPATH = Join-Path (Get-Location) 'backend'
& .\.venv\Scripts\python.exe -m uvicorn lpo.api:app --host 127.0.0.1 --port 8000

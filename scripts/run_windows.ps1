$ErrorActionPreference = "Stop"

Write-Host "run_windows.ps1 se conserva como alias. El proceso será administrado por portal.ps1."
$manager = Join-Path $PSScriptRoot "portal.ps1"
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $manager start
exit $LASTEXITCODE

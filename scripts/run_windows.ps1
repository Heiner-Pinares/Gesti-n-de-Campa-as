$ErrorActionPreference = "Stop"

if (-not (Test-Path .\secrets\oracle_password.txt)) {
    throw "Falta secrets\oracle_password.txt. Configure el secreto sin versionarlo."
}

$env:DB_ENGINE = "oracle"
$env:ORACLE_POOL = "false"
$env:AUTO_MIGRATE = "false"

& .\.venv\Scripts\python.exe run.py

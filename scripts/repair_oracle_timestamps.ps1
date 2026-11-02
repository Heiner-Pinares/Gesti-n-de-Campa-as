$ErrorActionPreference = "Stop"
$env:DB_ENGINE = "oracle"
$env:ORACLE_POOL = "false"
$env:AUTO_MIGRATE = "false"

& .\.venv\Scripts\python.exe manage.py reparar_fechas_gc --apply --confirmacion REPARAR_FECHAS_GC
if ($LASTEXITCODE -ne 0) { throw "No se pudo reparar la compatibilidad de fechas Oracle." }

Write-Host "Fechas GC compatibles con python-oracledb Thin."

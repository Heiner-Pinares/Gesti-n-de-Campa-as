$ErrorActionPreference = "Stop"
$env:DB_ENGINE = "oracle"
$env:ORACLE_POOL = "false"
$env:AUTO_MIGRATE = "false"

& .\.venv\Scripts\python.exe manage.py instalar_esquema_gc
if ($LASTEXITCODE -ne 0) { throw "No se pudo mostrar el plan del esquema Oracle." }

$ErrorActionPreference = "Stop"
$env:DB_ENGINE = "oracle"
$env:ORACLE_POOL = "false"
$env:AUTO_MIGRATE = "false"

& .\.venv\Scripts\python.exe manage.py crear_usuario_portal --rol ADMINISTRADOR
if ($LASTEXITCODE -ne 0) { throw "No se pudo crear el administrador del portal." }

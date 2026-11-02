$ErrorActionPreference = "Stop"
$env:DB_ENGINE = "oracle"
$env:ORACLE_POOL = "false"
$env:AUTO_MIGRATE = "false"

& .\.venv\Scripts\python.exe manage.py instalar_esquema_gc --apply --confirmacion CREAR_TABLAS_GC
if ($LASTEXITCODE -ne 0) { throw "La creación del esquema Oracle no terminó correctamente." }

Write-Host "Esquema GC comprobado. No se modificaron tablas fuente ni objetos 4DX."

$ErrorActionPreference = "Stop"
$env:DB_ENGINE = "oracle"
$env:ORACLE_POOL = "false"
$env:AUTO_MIGRATE = "false"

& .\.venv\Scripts\python.exe manage.py agregar_puesto_usuario_gc --apply --confirmacion AGREGAR_PUESTO_GC
if ($LASTEXITCODE -ne 0) { throw "No se pudo agregar el puesto del usuario al esquema GC." }

Write-Host "TBL_USUARIO_GC.PUESTO disponible para la sincronización con Active Directory."

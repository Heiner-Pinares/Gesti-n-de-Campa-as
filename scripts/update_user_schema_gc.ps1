$ErrorActionPreference = "Stop"
$env:DB_ENGINE = "oracle"
$env:ORACLE_POOL = "false"
$env:AUTO_MIGRATE = "false"

& .\.venv\Scripts\python.exe manage.py agregar_puesto_usuario_gc --apply --confirmacion AGREGAR_PUESTO_GC
if ($LASTEXITCODE -ne 0) { throw "No se pudo agregar el puesto del usuario al esquema GC." }

& .\.venv\Scripts\python.exe manage.py renombrar_rol_usuario_gc --apply --confirmacion RENOMBRAR_ROL_USUARIO_GC
if ($LASTEXITCODE -ne 0) { throw "No se pudo renombrar el rol básico a USUARIO." }

Write-Host "Esquema de usuarios actualizado: PUESTO separado y rol básico USUARIO."

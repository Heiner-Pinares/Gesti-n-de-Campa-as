$ErrorActionPreference = "Stop"
$env:DB_ENGINE = "oracle"
$env:ORACLE_POOL = "false"
$env:AUTO_MIGRATE = "false"

& .\.venv\Scripts\python.exe manage.py inspeccionar_oracle --output reports\oracle_metadata.json
if ($LASTEXITCODE -ne 0) {
    throw "La inspección Oracle falló. No se generó un informe válido."
}

Write-Host "El informe solo contiene metadatos y conteos; no contiene datos de clientes."

$ErrorActionPreference = "Stop"
$env:DB_ENGINE = "oracle"
$env:ORACLE_POOL = "false"

& .\.venv\Scripts\python.exe manage.py verificar_oracle

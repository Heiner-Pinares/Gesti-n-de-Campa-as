$ErrorActionPreference = "Stop"
$env:DB_ENGINE = "sqlite3"
$env:SECRET_KEY = "check-only-not-for-deployment"

& .\.venv\Scripts\python.exe manage.py check
& .\.venv\Scripts\python.exe -m pytest -q

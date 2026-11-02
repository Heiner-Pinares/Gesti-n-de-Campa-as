$ErrorActionPreference = "Stop"

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    throw "Python Launcher no está disponible. Instale Python 3.12 x64."
}

py -3.12 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
& .\.venv\Scripts\python.exe manage.py collectstatic --noinput

Write-Host "Dependencias y archivos estáticos preparados. No se ejecutaron migraciones, DDL ni conexiones Oracle."

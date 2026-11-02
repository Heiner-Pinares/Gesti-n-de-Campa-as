$ErrorActionPreference = "Stop"

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    throw "Python Launcher no está disponible. Instale Python 3.12 x64."
}

py -3.12 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt

Write-Host "Dependencias instaladas. No se ejecutaron migraciones ni conexiones Oracle."

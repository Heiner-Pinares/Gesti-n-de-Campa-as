param(
    [int]$Port = 0,
    [switch]$SkipPortCheck
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "portal_common.ps1")

try {
    $config = Get-PortalConfiguration -Port $Port
}
catch {
    Write-Host "[ERROR] configuracion: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

$errors = 0
function Write-StepError {
    param([string]$Name, [string]$Detail)
    $script:errors += 1
    Write-Host "[ERROR] ${Name}: $Detail" -ForegroundColor Red
}

Write-Host "Validando portal en $($config.Root)"
Write-Host "Puerto efectivo: $($config.Port) (se toma del parametro o del .env)."

if (-not (Test-Path -LiteralPath $config.EnvironmentPath -PathType Leaf)) {
    Write-StepError -Name "configuracion" -Detail "Falta el archivo .env."
}
if (-not (Test-Path -LiteralPath $config.Python -PathType Leaf)) {
    Write-StepError -Name "python" -Detail "Falta .venv\Scripts\python.exe. Ejecute scripts\setup_windows.ps1."
}
if (-not (Test-Path -LiteralPath $config.EntryPoint -PathType Leaf)) {
    Write-StepError -Name "codigo" -Detail "Falta run.py."
}
if ($errors -gt 0) {
    Write-Host "Validacion rechazada: $errors error(es) bloqueante(s)." -ForegroundColor Red
    exit 1
}

$env:PORTAL_PORT = [string]$config.Port
$env:WEB_BIND_ADDRESS = $config.BindAddress
$env:PORTAL_THREADS = [string]$config.Threads
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$env:AUTO_MIGRATE = "false"

& $config.Python -c "import django, waitress, whitenoise, oracledb, ldap3, openpyxl; from Crypto.Hash import MD4; MD4.new(b'portal').digest()"
if ($LASTEXITCODE -ne 0) {
    Write-StepError -Name "dependencias" -Detail "Falta una dependencia Python, ldap3 o el proveedor MD4."
}
else {
    Write-Host "[OK] dependencias: paquetes Python y MD4 disponibles." -ForegroundColor Green
}

if ($errors -eq 0) {
    & $config.Python $config.ManagePy check
    if ($LASTEXITCODE -ne 0) {
        Write-StepError -Name "django" -Detail "manage.py check encontro errores."
    }
    else {
        Write-Host "[OK] django: comprobaciones internas aprobadas." -ForegroundColor Green
    }
}

if ($errors -eq 0) {
    & $config.Python $config.ManagePy makemigrations --check --dry-run
    if ($LASTEXITCODE -ne 0) {
        Write-StepError -Name "migraciones" -Detail "Se detectaron cambios de modelos que exigirian una migracion no aprobada."
    }
    else {
        Write-Host "[OK] migraciones: no hay migraciones pendientes generadas por el portal." -ForegroundColor Green
    }
}

if ($errors -eq 0) {
    $productionArguments = @($config.ManagePy, "validar_produccion", "--port", [string]$config.Port)
    if ($SkipPortCheck) { $productionArguments += "--sin-comprobar-puerto" }
    & $config.Python @productionArguments
    if ($LASTEXITCODE -ne 0) {
        Write-StepError -Name "produccion" -Detail "La conexion, el esquema o el entorno no estan listos."
    }
}

if ($errors -eq 0) {
    & $config.Python $config.ManagePy collectstatic --noinput --verbosity 0
    if ($LASTEXITCODE -ne 0) {
        Write-StepError -Name "estaticos" -Detail "collectstatic no pudo escribir en STATIC_ROOT."
    }
    else {
        Write-Host "[OK] estaticos: archivos preparados en la salida exclusiva." -ForegroundColor Green
    }
}

if ($errors -gt 0) {
    Write-Host "Validacion rechazada: $errors error(es) bloqueante(s). Las advertencias no se cuentan como errores." -ForegroundColor Red
    exit 1
}

Write-Host "Validacion aprobada. Revise las ADVERTENCIAS antes de publicar." -ForegroundColor Green
exit 0

param(
    [Parameter(Mandatory = $true)][string]$Desde,
    [Parameter(Mandatory = $true)][string]$Hasta,
    [ValidateSet("MANUAL", "PROGRAMADA")][string]$Tipo = "PROGRAMADA",
    [string]$Usuario = ""
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path .\secrets\oracle_password.txt)) {
    throw "Falta secrets\oracle_password.txt."
}

$arguments = @(
    "manage.py", "validar_campanas",
    "--desde", $Desde,
    "--hasta", $Hasta,
    "--tipo", $Tipo
)
if ($Usuario) {
    $arguments += @("--usuario", $Usuario)
}

& .\.venv\Scripts\python.exe @arguments
if ($LASTEXITCODE -ne 0) {
    throw "La validación terminó con error."
}

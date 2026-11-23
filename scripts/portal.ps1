param(
    [Parameter(Position = 0)]
    [ValidateSet("start", "stop", "restart", "status", "logs", "validate")]
    [string]$Action = "status",
    [int]$Port = 0,
    [ValidateRange(1, 5000)]
    [int]$Tail = 100
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "portal_common.ps1")

try {
    $config = Get-PortalConfiguration -Port $Port
    Initialize-PortalDirectories -Configuration $config
}
catch {
    Write-Host "ERROR DE CONFIGURACIÓN: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

function Show-PortalLogs {
    param([int]$Lines)
    $metadata = Read-PortalMetadata -Configuration $config
    $files = @()
    if ($null -ne $metadata) {
        if ($metadata.standard_log) { $files += [string]$metadata.standard_log }
        if ($metadata.error_log) { $files += [string]$metadata.error_log }
    }
    if ($files.Count -eq 0) {
        $files = @(Get-ChildItem -LiteralPath $config.LogDirectory -Filter "portal-*.log" -File -ErrorAction SilentlyContinue |
            Sort-Object LastWriteTime -Descending |
            Select-Object -First 2 -ExpandProperty FullName)
    }
    if ($files.Count -eq 0) {
        Write-Host "Todavía no existen logs del portal."
        return
    }
    foreach ($file in $files) {
        if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { continue }
        Write-Host "`n--- $file ---" -ForegroundColor Cyan
        Get-Content -LiteralPath $file -Tail $Lines -Encoding UTF8 | ForEach-Object { Write-Host $_ }
    }
}

function Stop-ManagedPortal {
    $state = Get-PortalProcessState -Configuration $config
    if ($state.State -eq "Stopped") {
        Write-Host "Portal detenido: no existe un proceso administrado."
        return $true
    }
    if ($state.State -eq "Stale") {
        Write-Host "PID obsoleto detectado: $($state.Detail)" -ForegroundColor Yellow
        Clear-PortalRuntimeState -Configuration $config
        Write-Host "El estado obsoleto fue limpiado; no se terminó ningún proceso."
        return $true
    }
    if ($state.State -eq "Foreign") {
        Write-Host "SEGURIDAD: $($state.Detail) PID=$($state.ProcessId)." -ForegroundColor Red
        Clear-PortalRuntimeState -Configuration $config
        Write-Host "Solo se limpió el PID obsoleto. El otro proceso sigue intacto." -ForegroundColor Yellow
        return $false
    }

    Write-Host "Deteniendo únicamente el proceso verificado del portal (PID $($state.ProcessId))..."
    Stop-Process -Id $state.ProcessId -ErrorAction Stop
    try {
        Wait-Process -Id $state.ProcessId -Timeout 20 -ErrorAction Stop
    }
    catch {
        $current = Get-PortalProcessState -Configuration $config
        if ($current.State -eq "Stopped" -or $current.State -eq "Stale") {
            Clear-PortalRuntimeState -Configuration $config
            Write-Host "Portal detenido correctamente." -ForegroundColor Green
            return $true
        }
        if ($current.State -ne "Running" -or $current.ProcessId -ne $state.ProcessId) {
            Write-Host "No se aplicará terminación forzada porque la identidad del proceso cambió." -ForegroundColor Red
            return $false
        }
        Write-Host "El proceso no cerró a tiempo; se terminará el mismo PID previamente verificado." -ForegroundColor Yellow
        Stop-Process -Id $state.ProcessId -Force -ErrorAction Stop
        Wait-Process -Id $state.ProcessId -Timeout 10 -ErrorAction SilentlyContinue
    }
    Clear-PortalRuntimeState -Configuration $config
    Write-Host "Portal detenido correctamente." -ForegroundColor Green
    return $true
}

function Start-ManagedPortal {
    $state = Get-PortalProcessState -Configuration $config
    if ($state.State -eq "Running") {
        Write-Host "El portal ya está activo: PID $($state.ProcessId), $($config.LocalUrl)." -ForegroundColor Green
        return $true
    }
    if ($state.State -eq "Stale" -or $state.State -eq "Foreign") {
        Write-Host "Estado obsoleto detectado: $($state.Detail)" -ForegroundColor Yellow
        Clear-PortalRuntimeState -Configuration $config
        if ($state.State -eq "Foreign") {
            Write-Host "El proceso PID $($state.ProcessId) no pertenece al portal y no fue modificado." -ForegroundColor Yellow
        }
    }

    if (-not (Test-PortalPortAvailable -Port $config.Port)) {
        Write-Host "ERROR: el puerto $($config.Port) está ocupado. No se detendrá el proceso que lo utiliza." -ForegroundColor Red
        return $false
    }

    $env:PORTAL_PORT = [string]$config.Port
    $env:WEB_BIND_ADDRESS = $config.BindAddress
    $env:PORTAL_THREADS = [string]$config.Threads
    $env:PYTHONUTF8 = "1"
    $env:PYTHONIOENCODING = "utf-8"
    $env:AUTO_MIGRATE = "false"

    Write-Host "Ejecutando validación previa (sin migraciones ni autenticación real contra AD)..."
    $validationExitCode = Invoke-PortalValidationProcess -Configuration $config
    if ($validationExitCode -ne 0) {
        Write-Host "ERROR: el portal no se inició porque la validación previa falló." -ForegroundColor Red
        return $false
    }
    if (-not (Test-PortalPortAvailable -Port $config.Port)) {
        Write-Host "ERROR: el puerto $($config.Port) fue ocupado durante la validación." -ForegroundColor Red
        return $false
    }

    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $standardLog = Join-Path $config.LogDirectory "portal-$stamp.out.log"
    $errorLog = Join-Path $config.LogDirectory "portal-$stamp.error.log"
    $quotedEntryPoint = '"' + $config.EntryPoint + '"'
    $process = Start-Process -FilePath $config.Python `
        -ArgumentList @($quotedEntryPoint) `
        -WorkingDirectory $config.Root `
        -RedirectStandardOutput $standardLog `
        -RedirectStandardError $errorLog `
        -WindowStyle Hidden `
        -PassThru

    Write-PortalMetadata -Configuration $config -ProcessId $process.Id -StandardLog $standardLog -ErrorLog $errorLog
    Write-Host "Proceso iniciado en segundo plano (PID $($process.Id)). Esperando respuesta HTTP..."

    $ready = $false
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        Start-Sleep -Seconds 1
        $current = Get-PortalProcessState -Configuration $config
        if ($current.State -ne "Running") { break }
        try {
            $response = Invoke-WebRequest -Uri "$($config.LocalUrl)/login/" -UseBasicParsing -TimeoutSec 3
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 400) {
                $ready = $true
                break
            }
        }
        catch { }
    }

    if (-not $ready) {
        Write-Host "ERROR: el portal no respondió por HTTP dentro del tiempo esperado." -ForegroundColor Red
        Show-PortalLogs -Lines 80
        $failedState = Get-PortalProcessState -Configuration $config
        if ($failedState.State -eq "Running" -and $failedState.ProcessId -eq $process.Id) {
            Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
        }
        Clear-PortalRuntimeState -Configuration $config
        return $false
    }

    Write-Host "Portal activo en $($config.LocalUrl) (PID $($process.Id))." -ForegroundColor Green
    Write-Host "Puerto efectivo: $($config.Port). Origen: parámetro explícito o .env."
    Write-Host "Logs: $($config.LogDirectory)"
    return $true
}

switch ($Action) {
    "start" {
        if (Start-ManagedPortal) { exit 0 } else { exit 1 }
    }
    "stop" {
        if (Stop-ManagedPortal) { exit 0 } else { exit 1 }
    }
    "restart" {
        if (-not (Stop-ManagedPortal)) { exit 1 }
        if (Start-ManagedPortal) { exit 0 } else { exit 1 }
    }
    "status" {
        $state = Get-PortalProcessState -Configuration $config
        if ($state.State -eq "Running") {
            Write-Host "ACTIVO: PID $($state.ProcessId), URL local $($config.LocalUrl), puerto $($config.Port)." -ForegroundColor Green
            Write-Host "Logs: $($config.LogDirectory)"
            $metadata = Read-PortalMetadata -Configuration $config
            if ($null -ne $metadata) { Write-Host "Inicio registrado: $($metadata.started_at)" }
            exit 0
        }
        if ($state.State -eq "Stale") {
            Write-Host "DETENIDO con PID obsoleto: $($state.Detail)" -ForegroundColor Yellow
            Clear-PortalRuntimeState -Configuration $config
        }
        elseif ($state.State -eq "Foreign") {
            Write-Host "DETENIDO: el PID registrado pertenece a otro proceso y no fue terminado." -ForegroundColor Yellow
            Clear-PortalRuntimeState -Configuration $config
        }
        else {
            Write-Host "DETENIDO: no existe un proceso administrado."
        }
        exit 1
    }
    "logs" {
        Show-PortalLogs -Lines $Tail
        exit 0
    }
    "validate" {
        $state = Get-PortalProcessState -Configuration $config
        $skipPort = $state.State -eq "Running"
        $validationExitCode = Invoke-PortalValidationProcess -Configuration $config -SkipPortCheck:$skipPort
        exit $validationExitCode
    }
}

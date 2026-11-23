$ErrorActionPreference = "Stop"

$script:PortalProjectRoot = Split-Path -Parent $PSScriptRoot

function Get-DotEnvValues {
    param([Parameter(Mandatory = $true)][string]$Path)

    $values = @{}
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return $values
    }

    foreach ($rawLine in Get-Content -LiteralPath $Path -Encoding UTF8) {
        $line = $rawLine.Trim().TrimStart([char]0xFEFF)
        if (-not $line -or $line.StartsWith("#")) { continue }
        if ($line.StartsWith("export ")) { $line = $line.Substring(7).Trim() }
        $separator = $line.IndexOf("=")
        if ($separator -lt 1) { continue }

        $name = $line.Substring(0, $separator).Trim()
        $value = $line.Substring($separator + 1).Trim()
        if ($value.Length -ge 2) {
            $first = $value.Substring(0, 1)
            $last = $value.Substring($value.Length - 1, 1)
            if (($first -eq '"' -and $last -eq '"') -or ($first -eq "'" -and $last -eq "'")) {
                $value = $value.Substring(1, $value.Length - 2)
            }
        }
        $values[$name] = $value
    }
    return $values
}

function Get-FirstConfiguredValue {
    param(
        [Parameter(Mandatory = $true)][hashtable]$Values,
        [Parameter(Mandatory = $true)][string[]]$Names,
        [Parameter(Mandatory = $true)][AllowEmptyString()][string]$Default
    )

    foreach ($name in $Names) {
        $processValue = [Environment]::GetEnvironmentVariable($name, "Process")
        if (-not [string]::IsNullOrWhiteSpace($processValue)) { return $processValue.Trim() }
        if ($Values.ContainsKey($name) -and -not [string]::IsNullOrWhiteSpace($Values[$name])) {
            return ([string]$Values[$name]).Trim()
        }
    }
    return $Default
}

function Get-PortalConfiguration {
    param([int]$Port = 0)

    $root = $script:PortalProjectRoot
    $environmentPath = Join-Path $root ".env"
    $values = Get-DotEnvValues -Path $environmentPath
    $configuredPort = Get-FirstConfiguredValue -Values $values -Names @("PORTAL_PORT", "PORT", "WEB_PORT") -Default "8000"
    $resolvedPort = if ($Port -gt 0) { $Port } else { 0 }
    if ($resolvedPort -eq 0 -and -not [int]::TryParse($configuredPort, [ref]$resolvedPort)) {
        throw "El puerto configurado en .env no es un número válido."
    }
    if ($resolvedPort -lt 1 -or $resolvedPort -gt 65535) {
        throw "El puerto debe estar entre 1 y 65535."
    }

    $bindAddress = Get-FirstConfiguredValue -Values $values -Names @("WEB_BIND_ADDRESS", "HOST", "WEB_HOST") -Default "0.0.0.0"
    $threads = Get-FirstConfiguredValue -Values $values -Names @("PORTAL_THREADS", "THREADS", "WEB_THREADS") -Default "8"
    $runtimeDirectory = Join-Path $root "runtime-config\portal"
    $logDirectory = Join-Path $root "logs\portal"

    return [PSCustomObject]@{
        Root = $root
        EnvironmentPath = $environmentPath
        Python = Join-Path $root ".venv\Scripts\python.exe"
        EntryPoint = Join-Path $root "run.py"
        ManagePy = Join-Path $root "manage.py"
        RuntimeDirectory = $runtimeDirectory
        LogDirectory = $logDirectory
        PidFile = Join-Path $runtimeDirectory "portal.pid"
        MetadataFile = Join-Path $runtimeDirectory "portal.json"
        Port = $resolvedPort
        BindAddress = $bindAddress
        Threads = $threads
        LocalUrl = "http://127.0.0.1:$resolvedPort"
    }
}

function Initialize-PortalDirectories {
    param([Parameter(Mandatory = $true)]$Configuration)
    New-Item -ItemType Directory -Path $Configuration.RuntimeDirectory -Force | Out-Null
    New-Item -ItemType Directory -Path $Configuration.LogDirectory -Force | Out-Null
}

function Clear-PortalRuntimeState {
    param([Parameter(Mandatory = $true)]$Configuration)
    Remove-Item -LiteralPath $Configuration.PidFile -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $Configuration.MetadataFile -Force -ErrorAction SilentlyContinue
}

function Get-PortalProcessState {
    param([Parameter(Mandatory = $true)]$Configuration)

    if (-not (Test-Path -LiteralPath $Configuration.PidFile -PathType Leaf)) {
        return [PSCustomObject]@{ State = "Stopped"; ProcessId = $null; Process = $null; Detail = "No existe PID registrado." }
    }

    $pidText = (Get-Content -LiteralPath $Configuration.PidFile -Raw -Encoding UTF8).Trim()
    $processId = 0
    if (-not [int]::TryParse($pidText, [ref]$processId) -or $processId -le 0) {
        return [PSCustomObject]@{ State = "Stale"; ProcessId = $null; Process = $null; Detail = "El archivo PID no es válido." }
    }

    $process = Get-CimInstance Win32_Process -Filter "ProcessId = $processId" -ErrorAction SilentlyContinue
    if ($null -eq $process) {
        return [PSCustomObject]@{ State = "Stale"; ProcessId = $processId; Process = $null; Detail = "El proceso registrado ya no existe." }
    }

    $expectedPython = [IO.Path]::GetFullPath($Configuration.Python)
    $actualExecutable = if ($process.ExecutablePath) { [IO.Path]::GetFullPath($process.ExecutablePath) } else { "" }
    $commandLine = [string]$process.CommandLine
    $executableMatches = $actualExecutable.Equals($expectedPython, [StringComparison]::OrdinalIgnoreCase)
    $entryMatches = $commandLine.IndexOf($Configuration.EntryPoint, [StringComparison]::OrdinalIgnoreCase) -ge 0
    if (-not $executableMatches -or -not $entryMatches) {
        return [PSCustomObject]@{
            State = "Foreign"
            ProcessId = $processId
            Process = $process
            Detail = "El PID pertenece a otro ejecutable o a otra línea de comandos; no se tocará ese proceso."
        }
    }

    return [PSCustomObject]@{ State = "Running"; ProcessId = $processId; Process = $process; Detail = "Proceso del portal verificado." }
}

function Test-PortalPortAvailable {
    param([Parameter(Mandatory = $true)][int]$Port)

    $listener = New-Object System.Net.Sockets.TcpListener -ArgumentList @([Net.IPAddress]::Any, $Port)
    try {
        $listener.Server.ExclusiveAddressUse = $true
        $listener.Start()
        return $true
    }
    catch [Net.Sockets.SocketException] {
        return $false
    }
    finally {
        try { $listener.Stop() } catch { }
    }
}

function Read-PortalMetadata {
    param([Parameter(Mandatory = $true)]$Configuration)
    if (-not (Test-Path -LiteralPath $Configuration.MetadataFile -PathType Leaf)) { return $null }
    try {
        return Get-Content -LiteralPath $Configuration.MetadataFile -Raw -Encoding UTF8 | ConvertFrom-Json
    }
    catch {
        return $null
    }
}

function Write-PortalMetadata {
    param(
        [Parameter(Mandatory = $true)]$Configuration,
        [Parameter(Mandatory = $true)][int]$ProcessId,
        [Parameter(Mandatory = $true)][string]$StandardLog,
        [Parameter(Mandatory = $true)][string]$ErrorLog
    )
    $metadata = [ordered]@{
        process_id = $ProcessId
        executable = $Configuration.Python
        entry_point = $Configuration.EntryPoint
        port = $Configuration.Port
        bind_address = $Configuration.BindAddress
        started_at = [DateTimeOffset]::Now.ToString("o")
        standard_log = $StandardLog
        error_log = $ErrorLog
    }
    $metadata | ConvertTo-Json | Set-Content -LiteralPath $Configuration.MetadataFile -Encoding UTF8
    [string]$ProcessId | Set-Content -LiteralPath $Configuration.PidFile -Encoding UTF8
}

function Invoke-PortalValidationProcess {
    param(
        [Parameter(Mandatory = $true)]$Configuration,
        [switch]$SkipPortCheck
    )
    $validator = Join-Path $PSScriptRoot "validar_portal_windows.ps1"
    $arguments = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $validator, "-Port", [string]$Configuration.Port)
    if ($SkipPortCheck) { $arguments += "-SkipPortCheck" }
    & powershell.exe @arguments 2>&1 | ForEach-Object { Write-Host $_ }
    $exitCode = $LASTEXITCODE
    return [int]$exitCode
}

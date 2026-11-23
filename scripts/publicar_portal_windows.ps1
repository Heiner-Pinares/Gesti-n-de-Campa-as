param(
    [Parameter(Mandatory = $true)]
    [string]$ServiceAccount,
    [Parameter(Mandatory = $true)]
    [Uri]$PublicUrl,
    [int]$Port = 0,
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$TaskName,
    [switch]$AllowInternalHttp
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "portal_common.ps1")

function Stop-Publication {
    param([string]$Message)
    Write-Host "ERROR DE PUBLICACIÓN: $Message" -ForegroundColor Red
    exit 1
}

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Stop-Publication "Abra PowerShell como administrador para registrar la tarea programada."
}

try {
    $portWasExplicit = $Port -gt 0
    $config = Get-PortalConfiguration -Port $Port
}
catch {
    Stop-Publication $_.Exception.Message
}

if ($PublicUrl.Scheme -notin @("http", "https")) {
    Stop-Publication "PublicUrl debe usar http o https."
}
if ($PublicUrl.AbsolutePath -ne "/") {
    Stop-Publication "PublicUrl debe ser la raíz del portal, sin una ruta adicional."
}
if ($PublicUrl.Scheme -eq "http" -and -not $AllowInternalHttp) {
    Stop-Publication "HTTP requiere el switch -AllowInternalHttp y aprobación explícita para la red interna."
}
if ($PublicUrl.Port -ne $config.Port) {
    Stop-Publication "El puerto de PublicUrl ($($PublicUrl.Port)) no coincide con el puerto efectivo del portal ($($config.Port))."
}
if ($config.BindAddress -ne "0.0.0.0") {
    Stop-Publication "WEB_BIND_ADDRESS debe ser 0.0.0.0."
}

$environment = Get-DotEnvValues -Path $config.EnvironmentPath
$allowedHosts = Get-FirstConfiguredValue -Values $environment -Names @("ALLOWED_HOSTS") -Default ""
$allowedHostItems = @($allowedHosts.Split(",") | ForEach-Object { $_.Trim().ToLowerInvariant() } | Where-Object { $_ })
if ($allowedHostItems -notcontains "*" -and $allowedHostItems -notcontains $PublicUrl.Host.ToLowerInvariant()) {
    Stop-Publication "ALLOWED_HOSTS no contiene '$($PublicUrl.Host)'."
}

if ($PublicUrl.Scheme -eq "https") {
    $cookieSecure = Get-FirstConfiguredValue -Values $environment -Names @("COOKIE_SECURE") -Default "false"
    $proxyHttps = Get-FirstConfiguredValue -Values $environment -Names @("TRUST_PROXY_HTTPS") -Default "false"
    $trustedOrigins = Get-FirstConfiguredValue -Values $environment -Names @("CSRF_TRUSTED_ORIGINS") -Default ""
    $origin = "https://$($PublicUrl.Authority)"
    if ($cookieSecure.ToLowerInvariant() -ne "true") {
        Stop-Publication "Para HTTPS configure COOKIE_SECURE=true."
    }
    if ($proxyHttps.ToLowerInvariant() -ne "true") {
        Stop-Publication "Para HTTPS detrás del proxy configure TRUST_PROXY_HTTPS=true."
    }
    if (@($trustedOrigins.Split(",") | ForEach-Object { $_.Trim().ToLowerInvariant() }) -notcontains $origin.ToLowerInvariant()) {
        Stop-Publication "CSRF_TRUSTED_ORIGINS debe incluir $origin."
    }
}
else {
    Write-Host "ADVERTENCIA: se publicará HTTP interno. No exponga esta URL a Internet." -ForegroundColor Yellow
}

Write-Host "Validando el entorno antes de solicitar la contraseña de la cuenta de servicio..."
$portalManager = Join-Path $PSScriptRoot "portal.ps1"
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $portalManager validate -Port $config.Port
if ($LASTEXITCODE -ne 0) {
    Stop-Publication "La validación previa falló; la tarea existente no fue modificada."
}

$password = Read-Host "Contraseña de $ServiceAccount (no se guardará en archivos ni logs)" -AsSecureString
$passwordPointer = [IntPtr]::Zero
$plainPassword = $null
$temporaryTaskName = "$TaskName - validacion-$([Guid]::NewGuid().ToString('N').Substring(0, 8))"

try {
    $passwordPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($password)
    $plainPassword = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($passwordPointer)

    $portalScript = $portalManager
    $taskArguments = "-NoProfile -ExecutionPolicy Bypass -File `"$portalScript`" start"
    if ($portWasExplicit) {
        $taskArguments += " -Port $($config.Port)"
    }
    $action = New-ScheduledTaskAction `
        -Execute "powershell.exe" `
        -Argument $taskArguments `
        -WorkingDirectory $config.Root
    $trigger = New-ScheduledTaskTrigger -AtStartup
    $settings = New-ScheduledTaskSettingsSet `
        -StartWhenAvailable `
        -ExecutionTimeLimit (New-TimeSpan -Minutes 5) `
        -RestartCount 3 `
        -RestartInterval (New-TimeSpan -Minutes 2)

    Write-Host "Comprobando cuenta, contraseña y definición en una tarea temporal..."
    Register-ScheduledTask `
        -TaskName $temporaryTaskName `
        -Action $action `
        -Trigger $trigger `
        -Settings $settings `
        -User $ServiceAccount `
        -Password $plainPassword `
        -RunLevel Highest `
        -Force | Out-Null
    Unregister-ScheduledTask -TaskName $temporaryTaskName -Confirm:$false

    Write-Host "Registrando la tarea definitiva '$TaskName'..."
    Register-ScheduledTask `
        -TaskName $TaskName `
        -Action $action `
        -Trigger $trigger `
        -Settings $settings `
        -User $ServiceAccount `
        -Password $plainPassword `
        -RunLevel Highest `
        -Force | Out-Null
}
catch {
    Unregister-ScheduledTask -TaskName $temporaryTaskName -Confirm:$false -ErrorAction SilentlyContinue
    Stop-Publication "No se pudo registrar la tarea: $($_.Exception.Message)"
}
finally {
    if ($passwordPointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($passwordPointer)
    }
    $plainPassword = $null
    $password = $null
}

Initialize-PortalDirectories -Configuration $config
$portSource = if ($portWasExplicit) { "parámetro" } else { ".env" }
$publication = [ordered]@{
    task_name = $TaskName
    service_account = $ServiceAccount
    public_url = $PublicUrl.AbsoluteUri.TrimEnd("/")
    port = $config.Port
    port_source = $portSource
    script = Join-Path $PSScriptRoot "portal.ps1"
    published_at = [DateTimeOffset]::Now.ToString("o")
    note = "No contiene contraseñas. El Firewall de Windows no fue modificado."
}
$publication | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $config.RuntimeDirectory "publication.json") -Encoding UTF8

Write-Host "Tarea registrada para el arranque de Windows." -ForegroundColor Green
Write-Host "Cuenta: $ServiceAccount"
Write-Host "URL pública declarada: $($PublicUrl.AbsoluteUri.TrimEnd('/'))"
Write-Host "Puerto efectivo: $($config.Port)"
Write-Host "El script no abrió puertos ni modificó el Firewall de Windows." -ForegroundColor Yellow

if ((Get-PortalProcessState -Configuration $config).State -eq "Running") {
    Write-Host "Reiniciando el proceso administrado para verificar realmente la cuenta de servicio..."
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $portalManager stop -Port $config.Port
    if ($LASTEXITCODE -ne 0) {
        Stop-Publication "No se pudo detener de forma segura el proceso anterior. La tarea quedó registrada pero no se inició."
    }
}

Write-Host "Iniciando la tarea para comprobar la disponibilidad con la cuenta de servicio..."
Start-ScheduledTask -TaskName $TaskName
$available = $false
for ($attempt = 0; $attempt -lt 120; $attempt++) {
    Start-Sleep -Seconds 1
    $state = Get-PortalProcessState -Configuration $config
    if ($state.State -eq "Running") {
        try {
            $response = Invoke-WebRequest -Uri "$($config.LocalUrl)/login/" -UseBasicParsing -TimeoutSec 3
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 400) {
                $available = $true
                break
            }
        }
        catch { }
    }
    $taskInfo = Get-ScheduledTaskInfo -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($null -ne $taskInfo -and $taskInfo.LastRunTime -gt [DateTime]::MinValue -and $taskInfo.LastTaskResult -ne 267009 -and $attempt -gt 10) {
        if ($state.State -ne "Running") { break }
    }
}

if (-not $available) {
    $taskInfo = Get-ScheduledTaskInfo -TaskName $TaskName -ErrorAction SilentlyContinue
    Write-Host "ERROR: la tarea quedó registrada, pero el portal no respondió localmente." -ForegroundColor Red
    if ($null -ne $taskInfo) { Write-Host "Resultado de la tarea: $($taskInfo.LastTaskResult)" }
    Write-Host "Revise: .\scripts\portal.cmd logs" -ForegroundColor Yellow
    exit 1
}

Write-Host "Portal disponible localmente y preparado para el próximo arranque de Windows." -ForegroundColor Green
Write-Host "Acceso declarado: $($PublicUrl.AbsoluteUri.TrimEnd('/'))"

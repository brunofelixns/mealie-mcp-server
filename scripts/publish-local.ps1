#Requires -Version 5.1
<#
.SYNOPSIS
Launch the Linux release workflow from Windows, without a host Python install.
.EXAMPLE
.\scripts\publish-local.ps1 -Action Login
.EXAMPLE
.\scripts\publish-local.ps1 -Action Publish
#>
[CmdletBinding()]
param(
    [ValidateSet('Plan', 'Login', 'Verify', 'Publish')]
    [string]$Action = 'Plan',

    [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9-]{0,38}$')]
    [string]$GitHubUser = 'brunofelixns',

    [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9_.-]*$')]
    [string]$Container
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$workspace = '/workspaces/mealie-mcp-server'
$repository = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))

function Invoke-Docker {
    param([string[]]$DockerArguments, [string]$Failure = 'Docker no pudo completar la operacion.')
    & docker @DockerArguments
    if ($LASTEXITCODE -ne 0) { throw $Failure }
}

function Normalize-Source {
    param([string]$Path)
    $normalized = $Path.Replace('\', '/').TrimEnd('/')
    $normalized = $normalized -replace '^//\?/', ''
    $normalized = $normalized -replace '^/run/desktop/mnt/host/', '/' -replace '^/host_mnt/', '/'
    $normalized = $normalized -replace '^([A-Za-z]):/', '/$1/'
    return $normalized.ToLowerInvariant()
}

function Test-Checkout {
    param([string]$Candidate)
    # Inspect only mounts, never Config.Env or credentials.
    $raw = Invoke-Docker -DockerArguments @('inspect', '--format', '{{json .Mounts}}', $Candidate)
    # Direct assignment also unwraps JSON arrays in Windows PowerShell 5.1.
    $mounts = ConvertFrom-Json -InputObject ($raw -join "`n")
    foreach ($mount in $mounts) {
        if ($mount.Type -eq 'bind' -and $mount.Destination -eq $workspace) {
            Write-Verbose ("Checkout: {0} | Mount: {1}" -f (Normalize-Source $repository), (Normalize-Source $mount.Source))
        }
        if ($mount.Type -eq 'bind' -and $mount.Destination -eq $workspace -and
            (Normalize-Source $mount.Source) -eq (Normalize-Source $repository)) { return $true }
    }
    return $false
}

function Invoke-Dev {
    param([string[]]$Command, [switch]$Interactive, [string]$Failure = 'Fallo dentro del Dev Container; revisar el mensaje anterior.')
    $dockerArguments = @('exec', '--user', 'vscode', '--workdir', $workspace)
    if ($Interactive) { $dockerArguments += @('--interactive', '--tty') }
    $dockerArguments += @($selected) + $Command
    Invoke-Docker -DockerArguments $dockerArguments -Failure $Failure
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw 'No se encuentra Docker. Instala y abre Docker Desktop con contenedores Linux.'
}
$engine = Invoke-Docker -DockerArguments @('info', '--format', '{{.OSType}}') -Failure 'Abre Docker Desktop y espera a que termine de arrancar.'
if ($engine -ne 'linux') { throw 'Docker Desktop debe usar contenedores Linux.' }

if ($Container) {
    if (-not (Test-Checkout $Container)) { throw 'Ese contenedor no monta este repositorio. Revisa -Container.' }
    $selected = $Container
} else {
    $candidates = @(Invoke-Docker -DockerArguments @('ps', '--filter', 'label=com.docker.compose.service=dev', '--format', '{{.ID}}'))
    $matchingContainers = @($candidates | Where-Object { Test-Checkout $_ })
    if ($matchingContainers.Count -eq 0) { throw 'Abre el repositorio en VS Code y ejecuta Dev Containers: Reopen in Container. Despues repite este comando.' }
    if ($matchingContainers.Count -gt 1) { throw 'Hay varios Dev Containers para este checkout. Indica uno con -Container NOMBRE.' }
    $selected = $matchingContainers[0]
}

Write-Host "Dev Container: $selected | Accion: $Action"
if ($Action -eq 'Login') {
    Invoke-Dev -Command @('gh', '--version') -Failure 'Falta GitHub CLI. En VS Code ejecuta Dev Containers: Rebuild and Reopen in Container.'
    Write-Host "Autoriza la cuenta $GitHubUser en el navegador. Si no se abre, visita https://github.com/login/device e introduce el codigo mostrado por gh."
    Invoke-Dev -Interactive -Command @('gh', 'auth', 'login', '--hostname', 'github.com', '--web', '--git-protocol', 'https', '--scopes', 'write:packages') -Failure 'Login GitHub incompleto. Repite -Action Login desde una terminal PowerShell interactiva.'
    $identity = Invoke-Dev -Command @('gh', 'api', 'user', '--hostname', 'github.com', '--jq', '.login')
    if ($identity.Trim() -ine $GitHubUser) { throw "Se ha autorizado otra cuenta. Repite el login con $GitHubUser o indica -GitHubUser." }
    # This whole pipeline runs in Linux. No token enters PowerShell or a log.
    # GitHubUser is validated above: $1 cannot contain whitespace or shell syntax.
    $loginPipe = 'set -euo pipefail; gh auth token --hostname github.com --user $1 | docker login ghcr.io --username $1 --password-stdin'
    Invoke-Dev -Command @('bash', '--noprofile', '--norc', '-c', $loginPipe, '--', $GitHubUser) -Failure 'Docker no pudo iniciar sesion en GHCR. Revisa la cuenta y el permiso write:packages.'
    Write-Host 'Login GHCR completado. Para construir, probar y publicar: .\scripts\publish-local.ps1 -Action Publish'
} else {
    $releaseArguments = @('uv', 'run', 'python', 'scripts/publish_local.py')
    if ($Action -eq 'Plan') { $releaseArguments += @('--dry-run', '--publish') }
    if ($Action -eq 'Publish') { $releaseArguments += '--publish' }
    Invoke-Dev -Command $releaseArguments -Failure 'El flujo de release se ha detenido. Revisa el error y los logs; no se reintenta automaticamente.'
}

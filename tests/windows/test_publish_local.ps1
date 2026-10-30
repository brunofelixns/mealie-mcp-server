param([Parameter(Mandatory = $true)][string]$Launcher)

$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path (Split-Path $Launcher) '..'))
$global:LauncherTestState = @{}

function global:docker {
    $arguments = @($args)
    $state = $global:LauncherTestState
    $state.Calls.Add($arguments)
    $global:LASTEXITCODE = 0
    switch ($arguments[0]) {
        'info' { if ($state.Scenario -eq 'windows-engine') { 'windows' } else { 'linux' } }
        'ps' {
            'dev-one'
            if ($state.Scenario -eq 'ambiguous') { 'dev-two' }
        }
        'inspect' {
            $source = if ($state.Scenario -eq 'wrong-workspace') { '/another-checkout' } else { $state.Root }
            ConvertTo-Json -Compress -InputObject @(
                @{ Source = '/var/lib/docker/volumes/venv/_data'; Destination = '/workspaces/mealie-mcp-server/.venv'; Type = 'volume' },
                @{ Source = $source; Destination = '/workspaces/mealie-mcp-server'; Type = 'bind' }
            )
        }
        'exec' {
            $index = 0
            while ($index -lt $arguments.Count -and $arguments[$index] -notlike 'dev-*') { $index++ }
            $command = @($arguments[($index + 1)..($arguments.Count - 1)])
            if ($command[0] -eq 'gh') {
                if ($command[1] -eq '--version' -and $state.Scenario -eq 'missing-gh') { $global:LASTEXITCODE = 127 }
                elseif ($command[1] -eq 'api') { if ($state.Scenario -eq 'wrong-account') { 'another-user' } else { 'brunofelixns' } }
                elseif ($command[1] -eq 'auth' -and $command[2] -eq 'login' -and $state.Scenario -eq 'login-fails') { $global:LASTEXITCODE = 41 }
                elseif ($command[1] -eq 'auth' -and $command[2] -eq 'token') { throw 'Token must remain in the container pipeline' }
            }
            if ($command[0] -eq 'uv' -and $state.Scenario -eq 'release-fails') { $global:LASTEXITCODE = 42 }
            if ($command[0] -eq 'bash' -and $state.Scenario -eq 'registry-login-fails') { $global:LASTEXITCODE = 43 }
        }
        default { throw "Unexpected Docker operation: $($arguments[0])" }
    }
}

function Assert-True($Condition, $Message) { if (-not $Condition) { throw $Message } }
function Invoke-Launcher($Action) { & $Launcher -Action $Action *> $null }
function Assert-Fails($Action) {
    $failed = $false
    try { Invoke-Launcher $Action } catch { $failed = $true }
    Assert-True $failed "Expected $Action to fail"
}
function Get-ReleaseCalls { @($global:LauncherTestState.Calls | Where-Object { $_ -contains 'uv' }) }
function Get-LoginPipelines { @($global:LauncherTestState.Calls | Where-Object { $_ -contains 'bash' }) }

$cases = [ordered]@{
    'default only previews the publication' = {
        & $Launcher *> $null
        $calls = @(Get-ReleaseCalls)
        Assert-True ($calls.Count -eq 1) 'Expected one preview'
        Assert-True ($calls[0] -contains '--dry-run') 'Default must not publish'
    }
    'verify does not request publication' = {
        Invoke-Launcher Verify
        $calls = @(Get-ReleaseCalls)
        Assert-True ($calls.Count -eq 1 -and $calls[0] -notcontains '--publish') 'Verify requested publication'
    }
    'publish delegates to the existing Python gates without automatic login' = {
        Invoke-Launcher Publish
        $calls = @(Get-ReleaseCalls)
        Assert-True ($calls.Count -eq 1 -and $calls[0] -contains '--publish') 'Publish flag missing'
        Assert-True (@(Get-LoginPipelines).Count -eq 0) 'Publish must not log in automatically'
    }
    'login keeps the token pipeline and interactive browser flow inside Docker' = {
        Invoke-Launcher Login
        $pipelines = @(Get-LoginPipelines)
        Assert-True ($pipelines.Count -eq 1) 'Expected one container pipeline'
        Assert-True (($pipelines[0] -join ' ') -match 'pipefail.*gh auth token.*\| docker login.*--password-stdin') 'Unsafe token transfer'
        $interactive = @($global:LauncherTestState.Calls | Where-Object { $_ -contains 'login' -and $_ -contains 'gh' })
        Assert-True ($interactive.Count -eq 1 -and $interactive[0] -contains '--tty') 'Browser login needs interactive terminal'
        Assert-True (@(Get-ReleaseCalls).Count -eq 0) 'Login must not build or publish'
    }
    'a failed browser login stops before accessing credentials' = {
        $global:LauncherTestState.Scenario = 'login-fails'
        Assert-Fails Login
        Assert-True (@(Get-LoginPipelines).Count -eq 0) 'Login failure was ignored'
    }
    'a different GitHub account cannot log Docker in' = {
        $global:LauncherTestState.Scenario = 'wrong-account'
        Assert-Fails Login
        Assert-True (@(Get-LoginPipelines).Count -eq 0) 'Wrong account accepted'
    }
    'a registry login failure is propagated' = {
        $global:LauncherTestState.Scenario = 'registry-login-fails'
        Assert-Fails Login
    }
    'missing gh stops with no browser login or publication' = {
        $global:LauncherTestState.Scenario = 'missing-gh'
        Assert-Fails Login
        Assert-True (@(Get-LoginPipelines).Count -eq 0) 'Missing gh was ignored'
    }
    'release failure is propagated without retry' = {
        $global:LauncherTestState.Scenario = 'release-fails'
        Assert-Fails Publish
        Assert-True (@(Get-ReleaseCalls).Count -eq 1) 'Unexpected release retry'
    }
    'a container for a different checkout is rejected' = {
        $global:LauncherTestState.Scenario = 'wrong-workspace'
        Assert-Fails Publish
        Assert-True (@(Get-ReleaseCalls).Count -eq 0) 'Wrong checkout was used'
    }
    'ambiguous containers require explicit selection' = {
        $global:LauncherTestState.Scenario = 'ambiguous'
        Assert-Fails Publish
        Assert-True (@(Get-ReleaseCalls).Count -eq 0) 'Ambiguous checkout was used'
    }
    'an explicit container can be selected' = {
        & $Launcher -Action Plan -Container dev-explicit *> $null
        $calls = @(Get-ReleaseCalls)
        Assert-True ($calls.Count -eq 1 -and $calls[0] -contains 'dev-explicit') 'Explicit container ignored'
    }
    'Windows engine is rejected before executing application commands' = {
        $global:LauncherTestState.Scenario = 'windows-engine'
        Assert-Fails Publish
        Assert-True (@(Get-ReleaseCalls).Count -eq 0) 'Non-Linux Docker accepted'
    }
}

$failed = 0
foreach ($case in $cases.GetEnumerator()) {
    $global:LauncherTestState = @{ Root = $root; Calls = [Collections.Generic.List[object]]::new(); Scenario = 'ok' }
    try { & $case.Value; Write-Host "PASS $($case.Key)" }
    catch { $failed++; Write-Host "FAIL $($case.Key): $($_.Exception.Message)" }
}
if ($failed) { throw "$failed launcher checks failed" }
Write-Host "$($cases.Count) launcher checks passed; Docker and credentials simulated"

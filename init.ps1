[CmdletBinding()]
param(
    [ValidateSet('Setup', 'Verify', 'Start', 'Status', 'Stop')]
    [string]$Action = 'Start'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$ProjectRoot = $PSScriptRoot
$PythonExecutable = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
$HarnessServiceScript = Join-Path $ProjectRoot 'scripts\run_harness_service.py'
$SetupCommand = @('uv', 'sync', '--all-extras')
$VerifyCommand = @($PythonExecutable, (Join-Path $ProjectRoot 'scripts\verify.py'))
$SeedCommand = @($PythonExecutable, (Join-Path $ProjectRoot 'scripts\seed_database.py'), '--mode', 'apply')
$Services = @(
    [ordered]@{ Name = 'api'; Port = 8000; HealthUrl = 'http://127.0.0.1:8000/health' },
    [ordered]@{ Name = 'ui'; Port = 8501; HealthUrl = 'http://127.0.0.1:8501/_stcore/health' }
)

$HarnessDirectory = Join-Path $ProjectRoot 'data\harness'
$ProcessStateFile = Join-Path $HarnessDirectory 'processes.json'
$LegacyEnvironmentFile = Join-Path $ProjectRoot '.env'
$EnvironmentFile = Join-Path $ProjectRoot '.env.local'
Set-Location -LiteralPath $ProjectRoot

function Ensure-HarnessDirectory {
    if (-not (Test-Path -LiteralPath $HarnessDirectory -PathType Container)) {
        New-Item -ItemType Directory -Path $HarnessDirectory | Out-Null
    }
}

function Move-LegacyEnvironmentFile {
    $legacyExists = Test-Path -LiteralPath $LegacyEnvironmentFile -PathType Leaf
    $currentExists = Test-Path -LiteralPath $EnvironmentFile -PathType Leaf
    if ($legacyExists -and $currentExists) {
        throw 'Both .env and .env.local exist. Neither file was changed.'
    }
    if ($legacyExists) {
        Move-Item -LiteralPath $LegacyEnvironmentFile -Destination $EnvironmentFile
        Write-Host 'Renamed .env to .env.local without printing its values.'
    }
}

function Invoke-ConfiguredCommand {
    param([object[]]$Command)
    if ($Command.Count -lt 1) { throw 'The configured command is empty.' }
    $executable = $Command[0]
    $arguments = @($Command | Select-Object -Skip 1)
    & $executable @arguments
    if ($LASTEXITCODE -ne 0) { throw "Command failed with exit code $LASTEXITCODE." }
}

function Require-ProjectPython {
    if (-not (Test-Path -LiteralPath $PythonExecutable -PathType Leaf)) {
        throw 'The project Python executable was not found. Run .\init.ps1 -Action Setup first.'
    }
}

function Start-HarnessProcess {
    param([string]$ServiceName)

    $startInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $startInfo.FileName = $PythonExecutable
    $startInfo.Arguments = '"{0}" {1}' -f $HarnessServiceScript, $ServiceName
    $startInfo.WorkingDirectory = $ProjectRoot
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    $startInfo.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden

    Write-Host ("Launching {0} service..." -f $ServiceName)
    try {
        $process = [System.Diagnostics.Process]::Start($startInfo)
    }
    catch {
        throw (
            "Could not launch {0} with project Python at '{1}': {2}" -f
            $ServiceName, $PythonExecutable, $_.Exception.Message
        )
    }
    if ($null -eq $process) {
        throw "Could not launch $ServiceName because the process API returned no process."
    }
    return $process
}

function Get-ListeningProcessId {
    param([int]$Port)
    try {
        $connection = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction Stop |
            Select-Object -First 1
        if ($null -ne $connection) { return [int]$connection.OwningProcess }
    }
    catch { return $null }
    return $null
}

function Wait-ForHealth {
    param([string]$Url)
    $deadline = [DateTime]::UtcNow.AddSeconds(45)
    while ([DateTime]::UtcNow -lt $deadline) {
        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 300) { return $true }
        }
        catch { Start-Sleep -Milliseconds 350 }
    }
    return $false
}

function Get-State {
    if (-not (Test-Path -LiteralPath $ProcessStateFile -PathType Leaf)) { return $null }
    try { return Get-Content -LiteralPath $ProcessStateFile -Raw | ConvertFrom-Json }
    catch { return $null }
}

function Get-OwnedProcess {
    param($Record)
    try {
        $process = Get-Process -Id ([int]$Record.process_id) -ErrorAction Stop
        if ($process.StartTime.ToUniversalTime().ToFileTimeUtc() -ne
            [long]$Record.start_time_filetime_utc) { return $null }
        return $process
    }
    catch { return $null }
}

function Stop-HarnessRecords {
    param([object[]]$Records)

    for ($index = $Records.Count - 1; $index -ge 0; $index--) {
        $record = $Records[$index]
        $process = Get-OwnedProcess $record
        if ($null -ne $process) {
            Stop-Process -Id $process.Id -ErrorAction SilentlyContinue
            Write-Host ("Stopped {0} process {1}." -f $record.name, $process.Id)
        }
    }
    Remove-Item -LiteralPath $ProcessStateFile -Force -ErrorAction SilentlyContinue
}

function Invoke-Setup {
    Move-LegacyEnvironmentFile
    Invoke-ConfiguredCommand $SetupCommand
    Write-Host 'Setup complete.' -ForegroundColor Green
}

function Invoke-Verify {
    Move-LegacyEnvironmentFile
    Require-ProjectPython
    Invoke-ConfiguredCommand $VerifyCommand
    Write-Host 'Verification complete.' -ForegroundColor Green
}

function Invoke-Start {
    Move-LegacyEnvironmentFile
    Require-ProjectPython
    Ensure-HarnessDirectory
    foreach ($service in $Services) {
        $owner = Get-ListeningProcessId ([int]$service.Port)
        if ($null -ne $owner) { throw "Port $($service.Port) is already used by process $owner." }
    }

    Invoke-ConfiguredCommand $SeedCommand

    $started = @()
    try {
        foreach ($service in $Services) {
            $process = Start-HarnessProcess $service.Name
            if (-not (Wait-ForHealth $service.HealthUrl)) {
                throw "$($service.Name) did not become healthy."
            }
            $started += [ordered]@{
                name = $service.Name
                process_id = $process.Id
                start_time_filetime_utc = $process.StartTime.ToUniversalTime().ToFileTimeUtc()
                port = $service.Port
            }
        }
        [ordered]@{ project_root = $ProjectRoot; processes = $started } |
            ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $ProcessStateFile -Encoding UTF8
    }
    catch {
        Stop-HarnessRecords $started
        throw
    }

    Write-Host ''
    Write-Host 'Bright Path is running.' -ForegroundColor Green
    Write-Host 'Application:       http://127.0.0.1:8501' -ForegroundColor Cyan
    Write-Host 'API documentation: http://127.0.0.1:8000/docs' -ForegroundColor Cyan
    Write-Host 'Press Ctrl+C to stop Bright Path.' -ForegroundColor Yellow

    try {
        while ($true) {
            Start-Sleep -Seconds 1
            foreach ($record in $started) {
                if ($null -eq (Get-OwnedProcess $record)) {
                    throw "$($record.name) service stopped unexpectedly."
                }
            }
        }
    }
    finally {
        Write-Host ''
        Write-Host 'Stopping Bright Path...' -ForegroundColor Yellow
        Stop-HarnessRecords $started
    }
}

function Invoke-Status {
    $state = Get-State
    foreach ($service in $Services) {
        $owner = Get-ListeningProcessId ([int]$service.Port)
        $status = if ($null -eq $owner) { 'available' } else { "listening process $owner" }
        Write-Host ("{0} on port {1}: {2}" -f $service.Name, $service.Port, $status)
    }
    if ($null -eq $state) { Write-Host 'No harness-owned process state is recorded.' }
}

function Invoke-Stop {
    $state = Get-State
    if ($null -eq $state) { Write-Host 'Nothing to stop.'; return }
    Stop-HarnessRecords @($state.processes)
}

try {
    switch ($Action) {
        'Setup' { Invoke-Setup }
        'Verify' { Invoke-Verify }
        'Start' { Invoke-Start }
        'Status' { Invoke-Status }
        'Stop' { Invoke-Stop }
    }
}
catch {
    Write-Error $_.Exception.Message
    exit 1
}

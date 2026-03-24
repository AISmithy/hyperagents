[CmdletBinding()]
param(
    [switch]$KeepPidFiles
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$RunDir = Join-Path $Root ".run"

function Stop-TrackedProcess {
    param(
        [string]$Name,
        [string]$PidFile
    )

    if (-not (Test-Path $PidFile)) {
        Write-Host "$Name is not tracked."
        return
    }

    $raw = (Get-Content $PidFile -ErrorAction SilentlyContinue | Select-Object -First 1).Trim()
    $processId = 0
    if (-not [int]::TryParse($raw, [ref]$processId)) {
        Write-Host "$Name pid file is invalid."
        if (-not $KeepPidFiles) {
            Remove-Item $PidFile -ErrorAction SilentlyContinue
        }
        return
    }

    $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
    if ($process) {
        Stop-Process -Id $processId -Force
        Write-Host "Stopped $Name (PID $processId)."
    } else {
        Write-Host "$Name was not running."
    }

    if (-not $KeepPidFiles) {
        Remove-Item $PidFile -ErrorAction SilentlyContinue
    }
}

if (-not (Test-Path $RunDir)) {
    Write-Host ".run directory not found. Nothing to stop."
    exit 0
}

Stop-TrackedProcess -Name "backend" -PidFile (Join-Path $RunDir "backend.pid")
Stop-TrackedProcess -Name "frontend" -PidFile (Join-Path $RunDir "frontend.pid")

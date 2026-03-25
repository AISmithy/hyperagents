[CmdletBinding()]
param(
    [int]$BackendPort = 8011,
    [int]$FrontendPort = 4173
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendDir = Join-Path $Root "backend"
$FrontendDir = Join-Path $Root "frontend"
$RunDir = Join-Path $Root ".run"

New-Item -ItemType Directory -Force $RunDir | Out-Null

function Import-EnvFile {
    param([string]$Path)

    if (-not (Test-Path $Path)) {
        return
    }

    foreach ($line in Get-Content $Path) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#") -or -not $trimmed.Contains("=")) {
            continue
        }
        $parts = $trimmed.Split("=", 2)
        [Environment]::SetEnvironmentVariable($parts[0].Trim(), $parts[1].Trim(), "Process")
    }
}

function Get-RunningProcess {
    param([string]$PidFile)

    if (-not (Test-Path $PidFile)) {
        return $null
    }

    $raw = (Get-Content $PidFile -ErrorAction SilentlyContinue | Select-Object -First 1).Trim()
    if (-not $raw) {
        return $null
    }

    $processId = 0
    if (-not [int]::TryParse($raw, [ref]$processId)) {
        return $null
    }

    return Get-Process -Id $processId -ErrorAction SilentlyContinue
}

function Find-Python {
    $candidates = @(
        "C:\Users\nisha\AppData\Local\Programs\Python\Python311\python.exe",
        "C:\Users\nisha\AppData\Local\Programs\Python\Python312\python.exe",
        "C:\Users\nisha\AppData\Local\Programs\Python\Python310\python.exe"
    )

    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }

    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
        return $python.Source
    }

    throw "Python 3.11+ was not found. Install Python and rerun .\run.ps1."
}

function Find-Node {
    $candidates = @(
        "C:\Program Files\nodejs\node.exe",
        "C:\Program Files (x86)\nodejs\node.exe",
        (Join-Path $env:LOCALAPPDATA "Programs\nodejs\node.exe")
    )

    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }

    $node = Get-Command node -ErrorAction SilentlyContinue
    if ($node) {
        return $node.Source
    }

    throw "Node.js was not found. Install Node.js LTS and rerun .\run.ps1."
}

function Find-Npm {
    $candidates = @(
        "C:\Program Files\nodejs\npm.cmd",
        "C:\Program Files (x86)\nodejs\npm.cmd",
        (Join-Path $env:LOCALAPPDATA "Programs\nodejs\npm.cmd")
    )

    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }

    $npm = Get-Command npm -ErrorAction SilentlyContinue
    if ($npm) {
        return $npm.Source
    }

    throw "npm was not found. Install Node.js LTS and rerun .\run.ps1."
}

function Ensure-BackendDependencies {
    param([string]$PythonExe)

    & $PythonExe -c "import fastapi, uvicorn, openai" 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) {
        return
    }

    Write-Host "Installing backend dependencies..."
    & $PythonExe -m pip install -e . | Out-Host
    if ($LASTEXITCODE -ne 0) {
        throw "Backend dependency installation failed."
    }
}

function Ensure-FrontendDependencies {
    param([string]$NpmCmd, [string]$NodeExe)

    $nodeModules = Join-Path $FrontendDir "node_modules"
    if (Test-Path $nodeModules) {
        return
    }

    Write-Host "Installing frontend dependencies..."
    $env:Path = "$(Split-Path $NodeExe -Parent);$env:Path"
    & $NpmCmd install | Out-Host
    if ($LASTEXITCODE -ne 0) {
        throw "Frontend dependency installation failed."
    }
}

Import-EnvFile (Join-Path $Root ".env.local")
Import-EnvFile (Join-Path $BackendDir ".env.local")

$PythonExe = Find-Python
$NodeExe = Find-Node
$NpmCmd = Find-Npm

Push-Location $BackendDir
try {
    Ensure-BackendDependencies -PythonExe $PythonExe
} finally {
    Pop-Location
}

Push-Location $FrontendDir
try {
    Ensure-FrontendDependencies -NpmCmd $NpmCmd -NodeExe $NodeExe
} finally {
    Pop-Location
}

$envFile = Join-Path $FrontendDir ".env.local"
@"
VITE_API_BASE=http://127.0.0.1:$BackendPort/api
"@ | Set-Content $envFile

$backendPidFile = Join-Path $RunDir "backend.pid"
$frontendPidFile = Join-Path $RunDir "frontend.pid"
$backendOut = Join-Path $RunDir "backend.out.log"
$backendErr = Join-Path $RunDir "backend.err.log"
$frontendOut = Join-Path $RunDir "frontend.out.log"
$frontendErr = Join-Path $RunDir "frontend.err.log"

$backendProcess = Get-RunningProcess -PidFile $backendPidFile
if (-not $backendProcess) {
    $backendProcess = Start-Process `
        -FilePath $PythonExe `
        -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "$BackendPort" `
        -WorkingDirectory $BackendDir `
        -PassThru `
        -RedirectStandardOutput $backendOut `
        -RedirectStandardError $backendErr

    Set-Content $backendPidFile $backendProcess.Id
    Start-Sleep -Seconds 2
}

$frontendProcess = Get-RunningProcess -PidFile $frontendPidFile
if (-not $frontendProcess) {
    $frontendProcess = Start-Process `
        -FilePath $NodeExe `
        -ArgumentList ".\node_modules\vite\bin\vite.js", "--host", "127.0.0.1", "--port", "$FrontendPort", "--strictPort" `
        -WorkingDirectory $FrontendDir `
        -PassThru `
        -RedirectStandardOutput $frontendOut `
        -RedirectStandardError $frontendErr

    Set-Content $frontendPidFile $frontendProcess.Id
    Start-Sleep -Seconds 2
}

Write-Host ""
Write-Host "Hyperagents is running."
Write-Host "Frontend: http://127.0.0.1:$FrontendPort"
Write-Host "Backend:  http://127.0.0.1:$BackendPort/api/state"
Write-Host "Logs:     $RunDir"

param(
    [string]$RuntimeRoot = 'E:\Personal-Brain-V1-local'
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$postgresBin = Join-Path $RuntimeRoot 'postgres/Library/bin'
$pgCtl = Join-Path $postgresBin 'pg_ctl.exe'
$pgReady = Join-Path $postgresBin 'pg_isready.exe'
$dataDir = Join-Path $RuntimeRoot 'pgdata'
$secretDir = Join-Path $RuntimeRoot 'secrets'
$uv = (Get-Command uv -ErrorAction Stop).Source

foreach ($required in @($pgCtl, $pgReady, (Join-Path $secretDir 'db-dsn'),
        (Join-Path $secretDir 'token-pepper'), $dataDir)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "Windows local runtime is incomplete: $required"
    }
}

& $pgReady -h 127.0.0.1 -p 55432 | Out-Null
if ($LASTEXITCODE -ne 0) {
    & $pgCtl -D $dataDir -l (Join-Path $RuntimeRoot 'postgres.log') -o '-h 127.0.0.1 -p 55432' start
    if ($LASTEXITCODE -ne 0) { throw 'Local PostgreSQL did not start' }
}

$env:BRAIN_DATABASE_DSN_FILE = Join-Path $secretDir 'db-dsn'
$env:BRAIN_TOKEN_PEPPER_FILE = Join-Path $secretDir 'token-pepper'
$env:BRAIN_DATA_ROOT = Join-Path $RuntimeRoot 'data'
$env:BRAIN_BIND_HOST = '127.0.0.1'
$env:BRAIN_BIND_PORT = '18082'
$env:BRAIN_ENVIRONMENT = 'development'
$modelKey = Join-Path $secretDir 'model-api-key'
if ((Test-Path -LiteralPath $modelKey) -and (Get-Item -LiteralPath $modelKey).Length -gt 0) {
    $env:BRAIN_EXTERNAL_MODELS_ENABLED = 'true'
    $env:BRAIN_MODEL_API_KEY_FILE = $modelKey
} else {
    $env:BRAIN_EXTERNAL_MODELS_ENABLED = 'false'
    Remove-Item Env:\BRAIN_MODEL_API_KEY_FILE -ErrorAction SilentlyContinue
}
Remove-Item Env:\BRAIN_MODEL_PROXY_SOCKET -ErrorAction SilentlyContinue

Push-Location $projectRoot
try {
    & $uv run python -m personal_brain_server doctor --preflight --json
    if ($LASTEXITCODE -ne 0) { throw 'Local Brain preflight failed' }

    $workerPidFile = Join-Path $RuntimeRoot 'worker.pid'
    $workerRunning = $false
    if (Test-Path -LiteralPath $workerPidFile) {
        $workerPidValue = [IO.File]::ReadAllText($workerPidFile).Trim()
        if ($workerPidValue -match '^\d+$') {
            $workerRunning = $null -ne (Get-Process -Id ([int]$workerPidValue) -ErrorAction SilentlyContinue)
        }
    }
    if (-not $workerRunning) {
        $worker = Start-Process -FilePath $uv -ArgumentList @('run', 'python', '-m', 'personal_brain_worker') `
            -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru `
            -RedirectStandardOutput (Join-Path $RuntimeRoot 'worker.stdout.log') `
            -RedirectStandardError (Join-Path $RuntimeRoot 'worker.stderr.log')
        [IO.File]::WriteAllText($workerPidFile, [string]$worker.Id)
    }

    $apiPidFile = Join-Path $RuntimeRoot 'api.pid'
    $apiRunning = $false
    if (Test-Path -LiteralPath $apiPidFile) {
        $apiPidValue = [IO.File]::ReadAllText($apiPidFile).Trim()
        if ($apiPidValue -match '^\d+$') {
            $apiRunning = $null -ne (Get-Process -Id ([int]$apiPidValue) -ErrorAction SilentlyContinue)
        }
    }
    if (-not $apiRunning) {
        if (Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort 18082 -State Listen -ErrorAction SilentlyContinue) {
            throw 'Port 18082 is already in use by an unmanaged process'
        }
        $api = Start-Process -FilePath $uv -ArgumentList @('run', 'python', '-m', 'personal_brain_server') `
            -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru `
            -RedirectStandardOutput (Join-Path $RuntimeRoot 'api.stdout.log') `
            -RedirectStandardError (Join-Path $RuntimeRoot 'api.stderr.log')
        [IO.File]::WriteAllText($apiPidFile, [string]$api.Id)
    }

    $ready = $null
    for ($attempt = 0; $attempt -lt 15; $attempt++) {
        try {
            $ready = Invoke-RestMethod 'http://127.0.0.1:18082/ready' -TimeoutSec 2
            if ($ready.ready) { break }
        } catch { Start-Sleep -Milliseconds 500 }
    }
    if (-not $ready.ready) { throw 'Local Brain did not become ready' }
    Write-Output 'Personal Brain local runtime is ready at http://127.0.0.1:18082/ready'
} finally {
    Pop-Location
}

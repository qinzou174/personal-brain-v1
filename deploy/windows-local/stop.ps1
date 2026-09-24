param(
    [string]$RuntimeRoot = 'E:\Personal-Brain-V1-local'
)

$ErrorActionPreference = 'Stop'
$processes = @(Get-CimInstance Win32_Process)
foreach ($name in @('api', 'worker')) {
    $pidFile = Join-Path $RuntimeRoot "$name.pid"
    if (-not (Test-Path -LiteralPath $pidFile)) { continue }
    $pidValue = [IO.File]::ReadAllText($pidFile).Trim()
    if ($pidValue -match '^\d+$') {
        $root = $processes | Where-Object { $_.ProcessId -eq [int]$pidValue } | Select-Object -First 1
        if ($root -and $root.CommandLine -match 'personal_brain_(server|worker)') {
            $pending = @([int]$pidValue)
            $tree = @()
            while ($pending.Count -gt 0) {
                $current = $pending[0]
                $pending = @($pending | Select-Object -Skip 1)
                $tree += $current
                $pending += @($processes | Where-Object { $_.ParentProcessId -eq $current } |
                    Select-Object -ExpandProperty ProcessId)
            }
            [array]::Reverse($tree)
            foreach ($processId in $tree) {
                Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
            }
        }
    }
    Remove-Item -LiteralPath $pidFile
}
$pgCtl = Join-Path $RuntimeRoot 'postgres/Library/bin/pg_ctl.exe'
if (Test-Path -LiteralPath $pgCtl) {
    & $pgCtl -D (Join-Path $RuntimeRoot 'pgdata') stop -m fast
}

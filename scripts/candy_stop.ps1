# ============================================================
# Stop Candy — every process this project starts
# ============================================================
# Scoped on purpose. Other Python services run on this machine (the
# Kanban_Board API, an http.server on 5500), and a blanket "kill every
# python.exe" would take those down too. Pass -All to do that anyway.

[CmdletBinding()]
param(
    # Kill EVERY python process, not just Candy's. Destructive: this will
    # stop unrelated projects.
    [switch]$All
)

$ErrorActionPreference = 'SilentlyContinue'

$Ports = @(8000, 8899)
$Patterns = @('uvicorn\s+api\.index', 'http\.server\s+8899')

function Get-PythonProcesses {
    Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe'"
}

function Stop-Pid($processId, $why) {
    $p = Get-Process -Id $processId -ErrorAction SilentlyContinue
    if ($p) {
        Write-Host ("  stopping PID {0,-6} {1}" -f $processId, $why)
        Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
        return $true
    }
    return $false
}

Write-Host ""
Write-Host "Stopping Candy..." -ForegroundColor Cyan

if ($All) {
    Write-Host "  -All given: stopping EVERY python process on this machine." -ForegroundColor Yellow
    foreach ($p in Get-PythonProcesses) { Stop-Pid $p.ProcessId "(python.exe)" | Out-Null }
}
else {
    # 1. Anything whose command line is unmistakably Candy's.
    foreach ($p in Get-PythonProcesses) {
        foreach ($pattern in $Patterns) {
            if ($p.CommandLine -match $pattern) {
                Stop-Pid $p.ProcessId "($pattern)" | Out-Null
                break
            }
        }
    }

    # 2. Anything still listening on Candy's ports.
    foreach ($port in $Ports) {
        foreach ($conn in (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue)) {
            Stop-Pid $conn.OwningProcess "(listening on $port)" | Out-Null
        }
    }
}

Start-Sleep -Milliseconds 800

# 3. uvicorn --reload spawns a worker child. Kill the parent and the CHILD
#    keeps the listening socket, while Windows still reports the socket as
#    owned by the parent PID that no longer exists. Get-Process finds
#    nothing, the port stays busy, and the next launch fails with
#    WinError 10013. Hunt those orphans by their spawn_main command line.
foreach ($port in $Ports) {
    $conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    foreach ($conn in $conns) {
        $ownerAlive = Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue
        if (-not $ownerAlive) {
            Write-Host "  port $port held by dead PID $($conn.OwningProcess) - looking for its orphaned worker"
            foreach ($p in Get-PythonProcesses) {
                if ($p.CommandLine -match 'spawn_main' -and
                    $p.CommandLine -match "parent_pid=$($conn.OwningProcess)\b") {
                    Stop-Pid $p.ProcessId "(orphaned worker of $($conn.OwningProcess))" | Out-Null
                }
            }
        }
        else {
            Stop-Pid $conn.OwningProcess "(still on $port)" | Out-Null
        }
    }
}

Start-Sleep -Milliseconds 800

Write-Host ""
$busy = @()
foreach ($port in $Ports) {
    if (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) { $busy += $port }
}

if ($busy.Count -eq 0) {
    Write-Host "Candy stopped. Ports 8000 and 8899 are free." -ForegroundColor Green
}
else {
    Write-Host ("Still in use: {0}" -f ($busy -join ', ')) -ForegroundColor Red
    Write-Host "Find the holder with:" -ForegroundColor Yellow
    Write-Host '  Get-NetTCPConnection -LocalPort 8000 -State Listen | ForEach-Object { Get-CimInstance Win32_Process -Filter "ProcessId=$($_.OwningProcess)" } | Select-Object ProcessId, CommandLine'
}
Write-Host ""

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
$ConsoleTitles = @('Candy API', 'Candy UI')
# Must match frontend/index.html's <title> exactly - that's what Chrome's
# --app mode shows as the OS window title, since there's no tab strip to
# show it elsewhere. Built from a Unicode escape rather than typed as a
# literal em dash: a non-ASCII character embedded directly in a .ps1 file
# depends on the file having (and being read with) a matching encoding, and
# Windows PowerShell 5.1 parses a script without a BOM using the system
# codepage, not UTF-8 - a literal em dash silently became "Candyâ€”" the
# first time this ran, and the title match failed with no visible error.
$BrowserTitlePrefix = "Candy $([char]0x2014)"

# EnumWindows + PostMessage(WM_CLOSE) — done entirely in C#, not called from
# a PowerShell scriptblock. Passing a scriptblock as the EnumWindowsProc
# callback is unreliable in Windows PowerShell 5.1 (the delegate marshalling
# doesn't invoke it the way it looks like it should), and it failed silently
# here rather than throwing - the same trap the encoding bug above fell
# into: no output tells you it isn't matching anything.
#
# WM_CLOSE, not taskkill /FI WINDOWTITLE: that terminates the whole PROCESS
# owning the matched window - fine for "Candy API"/"Candy UI" (each cmd.exe
# owns exactly one console and nothing else), but wrong for Chrome, where
# one browser process can own several windows (Candy's app window plus any
# other Chrome window you have open) and TerminateProcess would take all of
# them down together. WM_CLOSE targets one window handle and asks only it
# to close, leaving every other window that process owns untouched.
#
# -TypeDefinition, not -MemberDefinition: -MemberDefinition wraps the given
# code as the BODY of a class it generates, so a `using` directive inside it
# is a compile error (`using` must sit outside the class). That error was
# also swallowed by $ErrorActionPreference above, so the type silently never
# existed and every call below silently did nothing - the same "no visible
# failure" trap twice in one script. Add -ErrorAction Stop plus a try/catch
# here so a third such failure prints something instead of vanishing.
if (-not ([System.Management.Automation.PSTypeName]'Candy.Win32').Type) {
    $win32Source = @'
using System;
using System.Text;
using System.Runtime.InteropServices;

namespace Candy {
    public static class Win32 {
        [DllImport("user32.dll")] private static extern bool EnumWindows(EnumWindowsProc lpEnumFunc, IntPtr lParam);
        [DllImport("user32.dll")] private static extern int GetWindowText(IntPtr hWnd, StringBuilder text, int count);
        [DllImport("user32.dll")] private static extern bool IsWindowVisible(IntPtr hWnd);
        [DllImport("user32.dll")] private static extern bool PostMessage(IntPtr hWnd, uint Msg, IntPtr wParam, IntPtr lParam);
        private delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);
        private const uint WM_CLOSE = 0x0010;

        public static int CloseByTitlePrefix(string prefix) {
            int closed = 0;
            EnumWindows((hWnd, lParam) => {
                if (IsWindowVisible(hWnd)) {
                    var sb = new StringBuilder(256);
                    GetWindowText(hWnd, sb, 256);
                    if (sb.ToString().StartsWith(prefix, StringComparison.Ordinal)) {
                        PostMessage(hWnd, WM_CLOSE, IntPtr.Zero, IntPtr.Zero);
                        closed++;
                    }
                }
                return true;
            }, IntPtr.Zero);
            return closed;
        }
    }
}
'@
    try {
        Add-Type -TypeDefinition $win32Source -ErrorAction Stop
    } catch {
        Write-Host "  [!] Window-closer helper failed to compile: $($_.Exception.Message)" -ForegroundColor Yellow
    }
}

function Close-WindowByTitlePrefix($prefix) {
    if (-not ([System.Management.Automation.PSTypeName]'Candy.Win32').Type) { return 0 }
    return [Candy.Win32]::CloseByTitlePrefix($prefix)
}

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

# 4. The "Candy API" / "Candy UI" console windows opened by `start "Title"
#    cmd /k ...`. Their python child is already dead by this point, but /k
#    leaves the empty cmd prompt sitting open - closing it here is what the
#    user actually asked for: no leftover windows to puzzle over.
#
#    `start "Title" ...` sets that string as the console WINDOW title, not
#    as a command-line argument, so it can't be found via CommandLine - the
#    same window-based closer used for the browser window below finds it.
foreach ($title in $ConsoleTitles) {
    if ((Close-WindowByTitlePrefix $title) -eq 0) {
        Write-Host "  console window '$title' already closed"
    }
}

# 5. Candy's dedicated Chrome window, closed by title so any OTHER Chrome
#    window or tab is left exactly as it was.
$closedWindows = Close-WindowByTitlePrefix $BrowserTitlePrefix
if ($closedWindows -eq 0) {
    Write-Host "  no Chrome window titled '$BrowserTitlePrefix*' found (already closed, or it opened in a different browser)"
}

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

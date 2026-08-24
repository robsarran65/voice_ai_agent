@echo off
rem ============================================================
rem  Stop Candy - the API, the web UI, and any orphaned workers
rem ============================================================
rem  Scoped to Candy's own processes. Other Python services run on this
rem  machine (Kanban_Board's API, an http.server on 5500), so a blanket
rem  "kill every python.exe" would take unrelated work down with it.
rem
rem  To kill EVERY python process anyway:  stop_candy.bat --all

setlocal
cd /d "%~dp0"
title Stop Candy

if /i "%~1"=="--all" goto killall
if /i "%~1"=="-all"  goto killall
if /i "%~1"=="/all"  goto killall

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\candy_stop.ps1"
goto done

:killall
echo.
echo   WARNING: this stops EVERY python process on this machine,
echo            including projects that have nothing to do with Candy.
echo.
choice /c YN /m "   Continue"
if errorlevel 2 goto cancelled
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\candy_stop.ps1" -All
goto done

:cancelled
echo   Cancelled - nothing was stopped.

:done
rem Hold the window open long enough to read. `timeout` is not used here: it
rem aborts with "Input redirection is not supported" whenever stdin isn't a
rem real console, which happens when this runs from a script or a task.
ping -n 6 127.0.0.1 >nul
endlocal

@echo off
rem ============================================================
rem  Start Candy - API, web UI, and the browser
rem ============================================================
rem  Local development only. Vercel serves this differently, per
rem  vercel.json - nothing here is used in a deployment.

setlocal
cd /d "%~dp0"
title Candy launcher

echo.
echo   Candy - MunAI Solutions LLC
echo   ----------------------------------------
echo.

rem --- The dual-Python trap: whichever "python" is first on PATH is the
rem     one that must have the packages, so check that exact one rather
rem     than assuming.
echo   Checking dependencies...
python -c "import fastapi, uvicorn, litellm, dotenv, httpx" 2>nul
if errorlevel 1 (
    echo.
    echo   [X] The 'python' on your PATH is missing packages Candy needs.
    echo       Install them into THAT interpreter:
    echo.
    echo         python -m pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

if not exist ".env" (
    echo.
    echo   [X] No .env file - Candy has no OPENROUTER_API_KEY and cannot answer.
    echo.
    pause
    exit /b 1
)

rem --- A port left busy by a previous run is the usual cause of
rem     "WinError 10013" on launch, so say so plainly instead of letting
rem     uvicorn fail with a misleading permissions error.
powershell -NoProfile -Command "if (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue) { exit 1 } else { exit 0 }"
if errorlevel 1 (
    echo.
    echo   [X] Port 8000 is already in use - Candy is probably already running.
    echo       Run stop_candy.bat first, then try again.
    echo.
    pause
    exit /b 1
)

echo   Starting API   ... http://127.0.0.1:8000
start "Candy API" cmd /k python -m uvicorn api.index:app --port 8000 --reload

echo   Starting web UI... http://127.0.0.1:8899
start "Candy UI" cmd /k python -m http.server 8899 --directory frontend

echo   Waiting for the API to answer...
powershell -NoProfile -Command "foreach ($i in 1..40) { try { Invoke-WebRequest -Uri 'http://127.0.0.1:8000/health/' -UseBasicParsing -TimeoutSec 1 | Out-Null; exit 0 } catch { Start-Sleep -Milliseconds 500 } }; exit 1"
if errorlevel 1 (
    echo.
    echo   [!] The API did not answer in 20 seconds. Check the "Candy API"
    echo       window for the error - the browser may show a backend error.
    echo.
) else (
    echo   API is up.
)

echo   Opening the browser...
start "" "http://127.0.0.1:8899/"

echo.
echo   Candy is running. Two windows opened:
echo     "Candy API"  - backend log, reloads when you edit Python
echo     "Candy UI"   - static file server
echo.
echo   Use Chrome on this desktop. Voice input needs Chrome's speech API,
echo   which iPhone and iPad do not have.
echo.
echo   Run stop_candy.bat to shut everything down.
echo.
rem Hold the window open long enough to read. `timeout` is not used here: it
rem aborts with "Input redirection is not supported" whenever stdin isn't a
rem real console, which happens when this runs from a script or a task.
ping -n 7 127.0.0.1 >nul
endlocal

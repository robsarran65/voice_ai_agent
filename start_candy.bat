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
rem     Import the Google libraries too. api/index.py pulls them in at import
rem     time via the tool layer, so if they're missing the API dies instantly
rem     and the only evidence is a traceback in a window that's easy to miss.
echo   Checking dependencies...
python -c "import fastapi, uvicorn, litellm, dotenv, httpx, googleapiclient, google_auth_oauthlib" 2>nul
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

rem     Catch anything else that breaks at import time - a syntax error in a
rem     module, a bad .env - while the message can still be shown here.
python -c "import api.index" 2>_startup_error.log
if errorlevel 1 (
    echo.
    echo   [X] Candy's API failed to load. The error was:
    echo.
    type _startup_error.log
    echo.
    pause
    exit /b 1
)
del _startup_error.log 2>nul

if not exist ".env" (
    echo.
    echo   [X] No .env file - Candy has no ANTHROPIC_API_KEY and cannot answer.
    echo.
    pause
    exit /b 1
)

rem --- Candy's voice input is Chrome-specific (webkitSpeechRecognition), but
rem     "start URL" opens whatever the OS DEFAULT browser is - Edge on this
rem     machine, where voice input doesn't work. Launching Chrome by its own
rem     path, rather than trusting the default, is what actually guarantees
rem     the right browser. It also gives stop_candy.bat one dedicated window
rem     it can find and close by title, instead of "whatever tab opened in
rem     whatever browser," which risks closing tabs that have nothing to do
rem     with Candy.
set "CHROME="
if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" set "CHROME=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
if "%CHROME%"=="" if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" set "CHROME=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
if "%CHROME%"=="" if exist "%LocalAppData%\Google\Chrome\Application\chrome.exe" set "CHROME=%LocalAppData%\Google\Chrome\Application\chrome.exe"

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
    echo   [X] The API never answered on port 8000.
    echo.
    echo       NOT opening the browser. A page served without a working
    echo       backend looks fine until you ask Candy something, and then
    echo       reports "I can't reach my backend from here" - which hides
    echo       the real error.
    echo.
    echo       Read the "Candy API" window: the reason is printed there.
    echo.
    pause
    exit /b 1
)

echo   API is up.

if "%CHROME%"=="" (
    echo.
    echo   [!] Chrome not found in its usual install locations.
    echo       Opening your default browser instead - voice input needs
    echo       Chrome specifically, so it may not work there. Install
    echo       Chrome for the full demo. stop_candy.bat also won't be able
    echo       to close this tab automatically, since it isn't Chrome.
    echo.
    start "" "http://127.0.0.1:8899/"
) else (
    echo   Opening Candy in its own Chrome window...
    rem --app runs Chrome without tabs/address bar/bookmarks - a dedicated
    rem window for Candy alone, so stop_candy.bat can find and close
    rem exactly this one by its page title without touching any other
    rem Chrome window or tab you have open.
    start "" "%CHROME%" --app=http://127.0.0.1:8899/ --new-window
)

echo.
echo   Candy is running. Three windows opened:
echo     "Candy API"  - backend log, reloads when you edit Python
echo     "Candy UI"   - static file server
echo     Candy's browser window
echo.
echo   Voice input needs Chrome's speech API, which iPhone and iPad don't
echo   have - this is a desktop-only demo for now.
echo.
echo   Run stop_candy.bat to shut all three down together.
echo.
rem Hold the window open long enough to read. `timeout` is not used here: it
rem aborts with "Input redirection is not supported" whenever stdin isn't a
rem real console, which happens when this runs from a script or a task.
ping -n 7 127.0.0.1 >nul
endlocal

@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul

echo ╔══════════════════════════════════════════╗
echo ║     KOKOOS AUTOMATED INSTALLER (Windows) ║
echo ╚══════════════════════════════════════════╝
echo.

:: ──────────────────────────────────────
:: STEP 1: Check Python Installation
:: ──────────────────────────────────────
where py >nul 2>&1 && set PYTHON=py || where python >nul 2>&1 && set PYTHON=python || (
    echo [❌] ERROR: Python is not installed or not in PATH.
    echo.
    echo Please install Python 3.10+ from https://www.python.org/downloads/
    echo Make sure to CHECK "Add Python to PATH" during installation!
    echo.
    pause
    exit /b 1
)

echo [✅] Found Python: 
%PYTHON% --version
echo.

:: ──────────────────────────────────────
:: STEP 2: Create Virtual Environment
:: ──────────────────────────────────────
if not exist ".venv" (
    echo [📦] Creating virtual environment in .venv ...
    %PYTHON% -m venv .venv
    if !errorlevel! neq 0 (
        echo [❌] ERROR: Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo [✅] Virtual environment created successfully.
) else (
    echo [ℹ️]  Virtual environment already exists in .venv
)

echo.

:: ──────────────────────────────────────
:: STEP 3: Activate Virtual Environment
:: ──────────────────────────────────────
echo [🔧] Activating virtual environment ...
call .venv\Scripts\activate.bat
if !errorlevel! neq 0 (
    echo [❌] ERROR: Failed to activate virtual environment.
    pause
    exit /b 1
)

:: ──────────────────────────────────────
:: STEP 4: Upgrade Pip & Install Dependencies
:: ──────────────────────────────────────
echo [📈] Upgrading pip ...
python -m pip install --upgrade pip --quiet

echo.
echo [⏳] Installing KOKOOS dependencies from requirements.txt ...
echo      This may take a few minutes, please be patient...
echo.
pip install -r requirements.txt
if !errorlevel! neq 0 (
    echo [❌] ERROR: Dependency installation failed. Check your network connection.
    pause
    exit /b 1
)
echo [✅] All Python packages installed successfully.

echo.

:: ──────────────────────────────────────
:: STEP 5: Install Playwright Browsers
:: ──────────────────────────────────────
echo [🌐] Installing Playwright browsers (needed for WebBrowserMCP & OutlookMCP) ...
playwright install chromium
if !errorlevel! neq 0 (
    echo [⚠️] WARNING: Playwright browser installation failed.
    echo      You can run "playwright install chromium" manually later.
) else (
    echo [✅] Playwright browsers installed successfully.
)

echo.

:: ──────────────────────────────────────
:: INSTALLATION COMPLETE!
:: ──────────────────────────────────────
echo ╔══════════════════════════════════════════╗
echo ║         INSTALLATION COMPLETE! 🎉        ║
echo ╚══════════════════════════════════════════╝
echo.
echo [📋] What's next?
echo ──────────────────────────────────────
echo.
echo 1️⃣  Activate the virtual environment (if needed):
echo      .venv\Scripts\activate.bat
echo.
echo 2️⃣  Boot ALL KOKOOS servers at once:
echo      boot_koko.bat
echo.
echo 3️⃣  Or run individual MCP servers:
echo      python CoderMCP.py             (Port 3020)
echo      python ComfyUIAudio.py         (Port 3018)
echo      python ComfyUIEdit.py          (Port 3017)
echo      python ComfyUIimage.py         (Port 3011)
echo      python DeepOSMCP.py            (Port 3022)
echo      python GmailMCP.py             (Port 3035)
echo      python hermes.py               (Main Shell)
echo      python JellyfinMCP.py          (Port 3010)
echo      python MemoryMCP.py            (Port 3021)
echo      python outlookmcp.py           (Port 3015)
echo      python WebBrowserMCP.py        (Port 3008)
echo      python YoutubePublisherMCP.py  (Port 3019)
echo.
echo 📝 NOTE: Edit .env file with your API keys before running!
echo          (Copy .env.example to .env if it doesn't exist)
echo.
pause >nul

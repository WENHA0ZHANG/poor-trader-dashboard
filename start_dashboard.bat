@echo off
REM Poor Trader Dashboard - Windows Portable Launcher

echo 🚀 Starting Poor Trader Dashboard...

REM Get script directory
set "SCRIPT_DIR=%~dp0"
set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
echo 📁 Project directory: %SCRIPT_DIR%

REM Check if virtual environment exists
if not exist "%SCRIPT_DIR%\trader" (
    echo ❌ Error: Virtual environment directory not found (%SCRIPT_DIR%\trader)
    echo 💡 Please ensure the entire project folder is copied to the target computer
    pause
    exit /b 1
)

REM Check if Python exists
if not exist "%SCRIPT_DIR%\trader\Scripts\python.exe" (
    if not exist "%SCRIPT_DIR%\trader\bin\python.exe" (
        echo ❌ Error: Python executable not found
        echo 💡 Please ensure virtual environment is complete
        pause
        exit /b 1
    )
)

REM Activate virtual environment (Windows)
echo 🐍 Activating virtual environment...
call "%SCRIPT_DIR%\trader\Scripts\activate.bat" 2>nul || call "%SCRIPT_DIR%\trader\bin\activate.bat" 2>nul
if errorlevel 1 (
    echo ❌ Virtual environment activation failed
    echo 💡 Please check if virtual environment is complete
    pause
    exit /b 1
)

REM Check database file
if not exist "%SCRIPT_DIR%\trader_alerts.sqlite3" (
    echo ⚠️  Database file does not exist, will be created automatically...
)

REM Start dashboard
echo.
echo 🌐 Starting dashboard service...
echo 📱 Access URL: http://127.0.0.1:8501
echo 🛑 Press Ctrl+C or close window to stop service
echo 📊 Database location: %SCRIPT_DIR%\trader_alerts.sqlite3
echo.

REM Change to project directory and start service
cd /d "%SCRIPT_DIR%"
trader serve --auto-fetch --providers "http,ycharts,cnn,multpl,nasdaqpe,fred,rsi"

REM If service stops, pause to show any error messages
pause

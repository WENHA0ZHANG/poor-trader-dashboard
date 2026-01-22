@echo off
REM Poor Trader Dashboard - Windows One-Click Launcher
REM Double-click this file to start the dashboard!

echo 🚀 Poor Trader Dashboard 启动器
echo ==================================================

REM 获取脚本所在目录
set "SCRIPT_DIR=%~dp0"
set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
echo 📂 项目位置: %SCRIPT_DIR%

REM Check if Python script exists
if not exist "%SCRIPT_DIR%\run_dashboard.py" (
    echo ❌ Error: run_dashboard.py file not found
    echo Please ensure files are complete
    pause
    exit /b 1
)

REM Check if Python exists
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Error: Python not found
    echo Please install Python 3.8 or higher
    echo Download: https://python.org
    pause
    exit /b 1
)

REM Run Python launcher script
echo 🐍 Starting Python script...
python "%SCRIPT_DIR%\run_dashboard.py"

REM 暂停以显示结果
pause

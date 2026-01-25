#!/bin/bash

# Poor Trader Dashboard - macOS One-Click Launcher
# Double-click this file to start the dashboard!

# Set window title
echo -n -e "\033]0;Poor Trader Dashboard\007"

echo "🚀 Poor Trader Dashboard Launcher"
echo "====================================="

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "📂 Project location: $SCRIPT_DIR"

# Check if project files exist
if [ ! -f "$SCRIPT_DIR/run_dashboard.py" ]; then
    echo "❌ Error: run_dashboard.py file not found"
    echo "Please ensure this script is in the same directory as project files"
    echo ""
    echo "Press any key to exit..."
    read -n 1
    exit 1
fi

# Check if Python exists
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found"
    echo "Please install Python 3.8 or higher"
    echo "Download: https://python.org"
    echo ""
    echo "Press any key to exit..."
    read -n 1
    exit 1
fi

echo "🐍 Python found: $(python3 --version)"

# Check virtual environment
if [ -d "$SCRIPT_DIR/trader" ]; then
    echo "✅ Virtual environment found"
else
    echo "⚠️  Virtual environment not found, will use system Python"
fi

# Change to project directory
cd "$SCRIPT_DIR"

# Run Python launcher script
echo ""
echo "🌐 Starting dashboard..."
echo "📱 Dashboard will open in browser window"
echo "🛑 To stop dashboard, close this window"
echo ""

# Run with default auto-fetch enabled (every 1 hour)
python3 run_dashboard.py

# If startup failed, keep window open
if [ $? -ne 0 ]; then
    echo ""
    echo "❌ Startup failed, please check error messages"
    echo "Press any key to exit..."
    read -n 1
fi

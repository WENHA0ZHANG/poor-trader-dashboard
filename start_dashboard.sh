#!/bin/bash

# Poor Trader Dashboard - Portable Launcher
# This script automatically detects the current directory without hardcoded paths

echo "🚀 Starting Poor Trader Dashboard..."

# Get script directory (portable version)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "📁 Project directory: $SCRIPT_DIR"

# Check if virtual environment exists
if [ ! -d "$SCRIPT_DIR/trader" ]; then
    echo "❌ Error: Virtual environment directory not found ($SCRIPT_DIR/trader)"
    echo "💡 Please ensure the entire project folder is copied to the target computer"
    exit 1
fi

# Activate virtual environment
echo "🐍 Activating virtual environment..."
source "$SCRIPT_DIR/trader/bin/activate"

# Check if virtual environment activation was successful
if [ "$VIRTUAL_ENV" != "" ]; then
    echo "✅ Virtual environment activated: $VIRTUAL_ENV"
else
    echo "❌ Virtual environment activation failed"
    echo "💡 Please check if Python virtual environment is complete"
    exit 1
fi

# Check if necessary files exist
if [ ! -f "$SCRIPT_DIR/trader_alerts.sqlite3" ]; then
    echo "⚠️  Database file does not exist, will be created automatically..."
fi

# Start dashboard
echo ""
echo "🌐 Starting dashboard service..."
echo "📱 Access URL: http://127.0.0.1:8501"
echo "🛑 Press Ctrl+C to stop service"
echo "📊 Database location: $SCRIPT_DIR/trader_alerts.sqlite3"
echo ""

# Start service (with auto-fetch feature)
cd "$SCRIPT_DIR"
trader serve --auto-fetch --providers "http,ycharts,cnn,vix,multpl,nasdaqpe,fred,rsi"

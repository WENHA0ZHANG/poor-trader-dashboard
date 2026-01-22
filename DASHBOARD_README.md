# Poor Trader Dashboard

A real-time financial indicators dashboard for stock market analysis.

## 🚀 Quick Start

### Method 1: Double-Click to Run (Easiest! 🎯)

#### macOS:
**双击** `run_dashboard.command` 文件 ✨
- 会自动打开终端窗口并启动仪表盘
- 仪表盘启动后会自动打开浏览器
- 要停止仪表盘，只需关闭终端窗口

#### Linux:
**双击** `run_dashboard.py` 文件
- 或者在终端运行: `python3 run_dashboard.py`

#### Windows:
**双击** `run_dashboard.cmd` 文件

### Method 2: Manual Scripts

**macOS/Linux:**
```bash
./start_dashboard.sh
```

**Windows:**
```cmd
start_dashboard.bat
```

These scripts will automatically:
- Detect the current directory
- Activate the virtual environment
- Start the dashboard on http://127.0.0.1:8501

### Method 2: Manual Commands
```bash
# 1. Go to project directory
cd /path/to/trader-dashboard

# 2. Activate virtual environment
source trader/bin/activate

# 3. Start dashboard
    trader serve --auto-fetch --providers "http,ycharts,cnn,vix,multpl,nasdaqpe,fred,rsi"
```

## 📦 Portable Distribution

This dashboard is designed to be **fully portable** - you can copy the entire folder to any computer and run it immediately.

### Sharing with Others

1. **Copy the entire project folder** to a USB drive or shared location
2. **Send the folder** to your friends/colleagues
3. **They just need to run** `./start_dashboard.sh` (macOS/Linux) or `start_dashboard.bat` (Windows)

### What Makes It Portable

- ✅ **Relative paths**: All file paths are relative to the project folder
- ✅ **Self-contained**: Includes Python virtual environment
- ✅ **Database**: SQLite database is stored locally in the project folder
- ✅ **No system dependencies**: Everything needed is included

## 🌐 Access Dashboard

Open your browser and go to: **http://127.0.0.1:8501**

## 📊 Features

- **Real-time Indicators**: US High Yield Spread, AAII Bull-Bear, CNN Fear & Greed, Put/Call Ratio, S&P 500 PE, Nasdaq 100 PE, RSI, VIX
- **Market Overview**: S&P 500, Dow Jones, Nasdaq, key stocks with percentage changes
- **Bull/Bear Alerts**: Top and bottom signals based on historical thresholds
- **Historical Analysis**: Major market tops/bottoms since 2000
- **Auto-refresh**: Automatic data fetching on page refresh

## 🛠️ Commands

```bash
# Show latest indicator values
trader show

# Fetch data manually
trader fetch all

# Evaluate alerts
trader evaluate

# Initialize templates
trader init
```

## 💻 System Requirements

- **macOS/Linux**: Bash shell
- **Windows**: Command Prompt or PowerShell
- **Network**: Internet connection for data fetching
- **Storage**: ~50MB free space

## 📁 Files

### 🚀 Launch Files
- `run_dashboard.command` - **macOS** (double-click! ⭐)
- `run_dashboard.cmd` - **Windows** (double-click!)
- `run_dashboard.py` - **Cross-platform Python script**
- `start_dashboard.sh` - macOS/Linux backup script
- `start_dashboard.bat` - Windows backup script

### 📊 Data & Config
- `trader_alerts.sqlite3` - Database file (auto-created)
- `api_config.yaml` - API configuration template
- `manual_input.yaml` - Manual data input template

### 🔧 Development
- `requirements.txt` - Python dependencies
- `requirements-web.txt` - Web dependencies (FastAPI, uvicorn)
- `trader/` - Python virtual environment
- `src/` - Source code
- `pyproject.toml` - Project configuration

## 🛑 Stop Service

- **macOS/Linux**: Press `Ctrl+C` in terminal
- **Windows**: Close the command window

## 🔧 Troubleshooting

### Dashboard doesn't start:
1. **Port conflict**: Check if port 8501 is available
2. **Python version**: Ensure Python 3.8+ is installed
3. **Virtual environment**: Ensure `trader/` folder exists and is complete
4. **Permissions**: Scripts need execute permissions on macOS/Linux
   ```bash
   chmod +x run_dashboard.py start_dashboard.sh
   ```
5. **Windows**: If double-clicking `.py` files doesn't work, use `run_dashboard.cmd`

### Data doesn't load:
1. **Internet connection**: Required for live data fetching
2. **Database**: Will auto-create if missing
3. **API keys**: Some indicators may need API keys (optional)

### Permission issues on macOS:
```bash
# Allow script execution
chmod +x start_dashboard.sh

# If virtual environment issues
xattr -rd com.apple.quarantine trader/
```

## 📞 Support

The dashboard provides real-time market sentiment analysis and historical context for informed trading decisions.

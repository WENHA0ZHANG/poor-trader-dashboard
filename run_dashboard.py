#!/usr/bin/env python3
"""
Poor Trader Dashboard - One-Click Launcher

Double-click this file to start the dashboard!

Supported platforms: macOS, Linux, Windows
"""

import os
import sys
import subprocess
import webbrowser
import time
import platform
from pathlib import Path

def print_banner():
    """Display startup banner"""
    print("🚀 Poor Trader Dashboard Launcher")
    print("=" * 50)

def detect_os():
    """Detect operating system"""
    system = platform.system().lower()
    if system == "darwin":
        return "macos"
    elif system == "windows":
        return "windows"
    elif system == "linux":
        return "linux"
    else:
        return "unknown"

def get_project_root():
    """Get project root directory"""
    # Get script directory
    script_dir = Path(__file__).parent.absolute()
    return script_dir

def check_virtual_env(project_root):
    """Check virtual environment"""
    venv_paths = [
        project_root / "trader",  # macOS/Linux
        project_root / "trader" / "Scripts",  # Windows
        project_root / "venv",
        project_root / "venv" / "Scripts",
        project_root / "env",
        project_root / "env" / "Scripts",
    ]

    for venv_path in venv_paths:
        if venv_path.exists():
            # Check Python executable
            python_exe = venv_path / "bin" / "python" if os.name != 'nt' else venv_path / "python.exe"
            if python_exe.exists():
                return str(python_exe), str(venv_path)

    return None, None

def check_requirements():
    """Check basic requirements"""
    issues = []

    # Check Python version
    if sys.version_info < (3, 8):
        issues.append(f"❌ Python version too low: {sys.version}. Need Python 3.8+")

    return issues

def check_and_cleanup_port(port=8501):
    """Check if port is in use and clean up residual processes"""
    import socket

    # Check if port is occupied
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(("127.0.0.1", port))
    sock.close()

    if result == 0:
        print(f"⚠️  Port {port} is already in use, cleaning up...")
        try:
            if platform.system() == "Windows":
                # Windows: Kill uvicorn processes
                subprocess.run(["taskkill", "/F", "/IM", "uvicorn.exe"],
                             capture_output=True, timeout=5)
                subprocess.run(["taskkill", "/F", "/IM", "python.exe"],
                             capture_output=True, timeout=5)
            else:
                # macOS/Linux: Kill related processes
                subprocess.run(["pkill", "-f", "uvicorn"],
                             capture_output=True, timeout=5)
                subprocess.run(["pkill", "-f", "trader.*serve"],
                             capture_output=True, timeout=5)

            print("✅ Cleaned up residual processes")
            time.sleep(2)  # Wait for cleanup to complete

        except Exception as e:
            print(f"⚠️  Auto cleanup failed: {e}")
            print("Please run manually: pkill -f uvicorn")
            return False

    return True

def activate_and_run(project_root, python_exe, venv_path):
    """Activate virtual environment and run dashboard"""
    try:
        print(f"📁 Project directory: {project_root}")
        print(f"🐍 Python path: {python_exe}")
        print(f"🌐 Virtual environment: {venv_path}")

        # Change to project directory
        os.chdir(project_root)

        # Check and cleanup port
        if not check_and_cleanup_port(8501):
            print("❌ Cannot cleanup port usage, please handle manually")
            return False

        # Check if trader command exists
        print("🔧 Checking application installation...")
        installed = False
        try:
            trader_cmd = [python_exe, "-c", "import trader_alerts.cli"]
            result = subprocess.run(trader_cmd, capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                print("⚠️  Installing application...")
                root_pyproject = Path(project_root) / "pyproject.toml"
                root_setup = Path(project_root) / "setup.py"
                src_pyproject = Path(project_root) / "src" / "pyproject.toml"
                src_setup = Path(project_root) / "src" / "setup.py"

                if root_pyproject.exists() or root_setup.exists():
                    install_cmd = [python_exe, "-m", "pip", "install", "-e", "."]
                elif src_pyproject.exists() or src_setup.exists():
                    install_cmd = [python_exe, "-m", "pip", "install", "-e", "src/"]
                else:
                    install_cmd = None
                    print("⚠️  No pyproject.toml or setup.py found, skipping install")

                if install_cmd:
                    subprocess.run(install_cmd, check=True, timeout=60)
                    installed = True
                    print("✅ Application installation completed")
        except subprocess.TimeoutExpired:
            print("⚠️  Installation timeout, continuing startup...")
        except Exception as e:
            print(f"⚠️  Installation check failed: {e}, continuing startup...")

        # Start dashboard service
        print("🌐 Starting dashboard service...")
        cmd = [
            python_exe, "-m", "uvicorn",
            "trader_alerts.web.app:app",
            "--host", "127.0.0.1",
            "--port", "8501",
            "--reload"
        ]

        print(f"📱 Dashboard URL: http://127.0.0.1:8501")
        print("🛑 Press Ctrl+C to stop service")
        print("")

        # Wait for service to start
        env = os.environ.copy()
        if not installed:
            src_path = str(Path(project_root) / "src")
            env["PYTHONPATH"] = f"{src_path}{os.pathsep}{env.get('PYTHONPATH', '')}"
        process = subprocess.Popen(cmd, env=env)

        # Wait for service startup
        time.sleep(3)

        # Auto open browser
        try:
            webbrowser.open("http://127.0.0.1:8501")
            print("✅ Browser opened automatically")
        except Exception as e:
            print(f"⚠️  Cannot open browser automatically: {e}")
            print("Please open manually: http://127.0.0.1:8501")

        # Wait for process to end
        process.wait()

    except KeyboardInterrupt:
        print("\n👋 Service stopped")
    except Exception as e:
        print(f"❌ Startup failed: {e}")
        return False

    return True

def main():
    """Main function"""
    print_banner()

    # Detect operating system
    os_type = detect_os()
    print(f"💻 Detected OS: {os_type}")

    # Check basic requirements
    issues = check_requirements()
    if issues:
        for issue in issues:
            print(issue)
        print("\nPlease resolve the above issues and try again.")
        input("Press Enter to exit...")
        return

    # Get project root directory
    project_root = get_project_root()
    print(f"📂 Project location: {project_root}")

    # Check virtual environment
    python_exe, venv_path = check_virtual_env(project_root)
    if not python_exe:
        print("❌ Virtual environment not found!")
        print("Please ensure the project folder contains a complete virtual environment.")
        print("Virtual environment should be in one of these locations:")
        print("  - trader/ (macOS/Linux)")
        print("  - trader/Scripts/ (Windows)")
        print("  - venv/")
        print("  - env/")
        input("Press Enter to exit...")
        return

    print("✅ Virtual environment found")

    # Check if test mode
    if "--test" in sys.argv:
        print("🧪 Test mode: Environment check passed!")
        print(f"🐍 Python: {python_exe}")
        print(f"🌐 Virtual environment: {venv_path}")
        print("✅ Dashboard service can be started")
        return

    # Start dashboard
    success = activate_and_run(project_root, python_exe, venv_path)

    if not success:
        print("\n❌ Startup failed")
        print("Please check error messages and try again.")
        input("Press Enter to exit...")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"💥 Unexpected error occurred: {e}")
        import traceback
        traceback.print_exc()
        input("Press Enter to exit...")

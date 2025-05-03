import subprocess
import platform
import sys

def install_dependencies():
    """Install required system and Python dependencies."""
    # Check and install Python package: rich
    try:
        from rich import print as rich_print
    except ImportError:
        print("Installing rich...")
        subprocess.run([sys.executable, "-m", "pip", "install", "rich"], check=True)

    # Check and install Python package: python-dotenv
    try:
        from dotenv import load_dotenv
    except ImportError:
        print("Installing python-dotenv...")
        subprocess.run([sys.executable, "-m", "pip", "install", "python-dotenv"], check=True)

    # Check and install system package: redsocks
    if platform.system() == "Windows":
        # For Windows, redsocks might need a different approach
        print("Note: redsocks is primarily a Linux tool. On Windows, you may need an alternative.")
        print("Consider using a Windows port or an alternative like Proxifier.")
    else:
        # Linux/Unix installation
        try:
            subprocess.run(["redsocks", "--version"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("Installing redsocks...")
            subprocess.run(["apt-get", "update"], check=True)
            subprocess.run(["apt-get", "install", "-y", "redsocks"], check=True)
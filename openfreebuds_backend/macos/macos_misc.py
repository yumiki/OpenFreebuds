"""
Miscellaneous macOS-specific functionality
"""
import subprocess
import os
from openfreebuds_backend.exception import BackendException

def get_system_info():
    """
    Get macOS system information
    """
    try:
        # Get macOS version
        os_version = subprocess.check_output(["sw_vers", "-productVersion"]).decode().strip()
        return {
            "os": "macOS",
            "version": os_version
        }
    except Exception as e:
        raise BackendException(f"Failed to get system info: {str(e)}")

def show_notification(title, message):
    """
    Show a system notification on macOS
    """
    try:
        # Use osascript to show a notification
        os.system(f'osascript -e \'display notification "{message}" with title "{title}"\'')
        return True
    except Exception as e:
        raise BackendException(f"Failed to show notification: {str(e)}")

def get_app_storage_path():
    """
    Returns the path where application data should be stored on macOS.
    
    On macOS, application data is typically stored in ~/Library/Application Support/[AppName]
    """
    import pathlib
    
    # Check if we're in portable mode (similar to Windows implementation)
    import sys
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # Running as a PyInstaller bundle
        executable_path = pathlib.Path(sys.executable)
        if (executable_path.parent / "portable_mode").exists():
            return executable_path.parent / "data"
    
    # Standard macOS application data location
    return pathlib.Path.home() / "Library" / "Application Support" / "openfreebuds"

# Add other macOS-specific functions as needed
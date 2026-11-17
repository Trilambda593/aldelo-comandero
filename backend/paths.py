import os
import sys

def get_base_dir() -> str:
    """Returns the bundled resources directory (sys._MEIPASS for PyInstaller, or project root)."""
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def get_app_dir() -> str:
    """Returns the directory where the .exe or project root is located (for persisting user config)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def get_static_dir() -> str:
    """Returns static folder path, supporting external folder next to .exe or bundled fallback."""
    custom = os.path.join(get_app_dir(), "static")
    if os.path.exists(custom):
        return custom
    return os.path.join(get_base_dir(), "static")

def get_config_path() -> str:
    return os.path.join(get_app_dir(), "config.json")

def get_printer_config_path() -> str:
    return os.path.join(get_app_dir(), "printer_config.json")

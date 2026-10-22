"""Windows Startup registration manager."""

import os
import sys
from pathlib import Path
from typing import Optional
import winreg

from storage.logger import logger

RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_REG_NAME = "AlexVoiceAssistant"


def get_default_startup_command() -> str:
    """Returns the command line string to run Alex on Windows startup."""
    if getattr(sys, "frozen", False):
        # Packaged Alex.exe
        exe_path = sys.executable
        return f'"{exe_path}" --tray'
    else:
        # Running from Python script / virtual environment
        python_exe = sys.executable
        app_script = str(Path(__file__).resolve().parent.parent / "app.py")
        return f'"{python_exe}" "{app_script}" --tray'


def is_startup_enabled() -> bool:
    """Checks whether Alex is currently configured to run on Windows startup."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, winreg.KEY_READ) as key:
            value, _ = winreg.QueryValueEx(key, APP_REG_NAME)
            return bool(value)
    except FileNotFoundError:
        return False
    except OSError as e:
        logger.error("Failed to read startup registry key: %s", e)
        return False


def enable_startup(custom_command: Optional[str] = None) -> bool:
    """Adds Alex to Windows HKCU Run registry key."""
    cmd = custom_command or get_default_startup_command()
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, APP_REG_NAME, 0, winreg.REG_SZ, cmd)
            logger.info("Enabled Windows startup: %s", cmd)
            return True
    except OSError as e:
        logger.error("Failed to enable Windows startup: %s", e)
        return False


def disable_startup() -> bool:
    """Removes Alex from Windows HKCU Run registry key."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, winreg.KEY_SET_VALUE) as key:
            try:
                winreg.DeleteValue(key, APP_REG_NAME)
                logger.info("Disabled Windows startup.")
                return True
            except FileNotFoundError:
                return True
    except OSError as e:
        logger.error("Failed to disable Windows startup: %s", e)
        return False


def toggle_startup(enable: bool) -> bool:
    """Toggles Windows startup on or off."""
    return enable_startup() if enable else disable_startup()

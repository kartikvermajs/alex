"""Application registry, auto-detection, and lifecycle manager."""

from dataclasses import dataclass, field
import os
from pathlib import Path
import shutil
import time
from typing import Dict, List, Optional, Tuple
import winreg

from storage.logger import logger
from system.process_manager import ProcessManager


@dataclass
class AppInfo:
    key: str
    display_name: str
    process_names: List[str]
    launch_command: str
    aliases: List[str] = field(default_factory=list)

    def matches_alias(self, query: str) -> bool:
        q = query.strip().lower()
        if q == self.key.lower() or q == self.display_name.lower():
            return True
        for alias in self.aliases:
            if q == alias.lower() or alias.lower() in q:
                return True
        return False


class ApplicationManager:
    """Manages application registration, discovery, opening, closing, and restarting."""

    def __init__(self):
        self._apps: Dict[str, AppInfo] = {}
        self._init_default_apps()
        self._auto_detect_apps()

    def _init_default_apps(self) -> None:
        """Configures baseline known applications."""
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        system_root = os.environ.get("SystemRoot", r"C:\Windows")

        defaults = [
            AppInfo(
                key="spotify",
                display_name="Spotify",
                process_names=["Spotify.exe", "SpotifyLauncher.exe"],
                launch_command=os.path.join(local_app_data, r"Microsoft\WindowsApps\Spotify.exe")
                if os.path.exists(os.path.join(local_app_data, r"Microsoft\WindowsApps\Spotify.exe"))
                else "spotify",
                aliases=["spotify", "spotify app", "music"],
            ),
            AppInfo(
                key="chrome",
                display_name="Chrome",
                process_names=["chrome.exe"],
                launch_command=r"C:\Program Files\Google\Chrome\Application\chrome.exe"
                if os.path.exists(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
                else "chrome",
                aliases=["chrome", "google chrome", "web browser", "browser"],
            ),
            AppInfo(
                key="notepad",
                display_name="Notepad",
                process_names=["notepad.exe"],
                launch_command=os.path.join(system_root, r"system32\notepad.exe"),
                aliases=["notepad", "text editor"],
            ),
            AppInfo(
                key="calculator",
                display_name="Calculator",
                process_names=["calc.exe", "CalculatorApp.exe"],
                launch_command=os.path.join(system_root, r"system32\calc.exe"),
                aliases=["calculator", "calc"],
            ),
            AppInfo(
                key="explorer",
                display_name="File Explorer",
                process_names=["explorer.exe"],
                launch_command="explorer.exe",
                aliases=["file explorer", "explorer", "files", "my files", "my computer"],
            ),
            AppInfo(
                key="brave",
                display_name="Brave",
                process_names=["brave.exe"],
                launch_command=r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
                aliases=["brave", "brave browser"],
            ),
            AppInfo(
                key="vlc",
                display_name="VLC",
                process_names=["vlc.exe"],
                launch_command=r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe",
                aliases=["vlc", "vlc media player", "media player"],
            ),
            AppInfo(
                key="discord",
                display_name="Discord",
                process_names=["Discord.exe"],
                launch_command=os.path.join(local_app_data, r"Discord\Update.exe --processStart Discord.exe"),
                aliases=["discord"],
            ),
        ]

        for app in defaults:
            self._apps[app.key] = app

    def _auto_detect_apps(self) -> None:
        """Scans Windows App Paths registry to discover installed desktop software."""
        roots = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"),
        ]

        for hkey, subkey_path in roots:
            try:
                with winreg.OpenKey(hkey, subkey_path) as key:
                    count, _, _ = winreg.QueryInfoKey(key)
                    for i in range(count):
                        try:
                            subkey_name = winreg.EnumKey(key, i)
                            with winreg.OpenKey(key, subkey_name) as app_key:
                                exe_path, _ = winreg.QueryValueEx(app_key, "")
                                if exe_path and os.path.exists(exe_path):
                                    base_name = Path(subkey_name).stem.lower()
                                    if base_name not in self._apps:
                                        self._apps[base_name] = AppInfo(
                                            key=base_name,
                                            display_name=base_name.capitalize(),
                                            process_names=[subkey_name],
                                            launch_command=exe_path,
                                            aliases=[base_name],
                                        )
                        except (OSError, ValueError):
                            continue
            except (OSError, PermissionError):
                continue

    def register_app(self, app_info: AppInfo) -> None:
        """Registers or overrides an application configuration."""
        self._apps[app_info.key] = app_info

    def get_all_apps(self) -> List[AppInfo]:
        """Returns all configured applications."""
        return list(self._apps.values())

    def find_app(self, query: str) -> Optional[AppInfo]:
        """Looks up an application by name or alias."""
        clean_query = query.strip().lower()
        if not clean_query:
            return None

        # Exact key match
        if clean_query in self._apps:
            return self._apps[clean_query]

        # Alias match
        for app in self._apps.values():
            if app.matches_alias(clean_query):
                return app

        # Substring search
        for app in self._apps.values():
            if clean_query in app.display_name.lower() or app.key in clean_query:
                return app

        return None

    def is_running(self, app_name_or_info: AppInfo | str) -> bool:
        """Checks if the application is currently running."""
        app = app_name_or_info if isinstance(app_name_or_info, AppInfo) else self.find_app(app_name_or_info)
        if not app:
            return False
        return ProcessManager.is_running(app.process_names)

    def open_app(self, query: str) -> Tuple[bool, str]:
        """Opens the requested application and verifies execution."""
        app = self.find_app(query)
        if not app:
            logger.warning("Application not found for query: %s", query)
            return False, f"I can't find {query} on this computer."

        if ProcessManager.is_running(app.process_names):
            logger.info("%s is already running.", app.display_name)
            return True, f"{app.display_name} is already open."

        success = ProcessManager.launch(
            launch_command=app.launch_command,
            verify_process_names=app.process_names,
            verify_timeout=5.0,
        )

        if success:
            return True, f"{app.display_name} is open."
        else:
            return False, f"{app.display_name} couldn't be opened."

    def close_app(self, query: str) -> Tuple[bool, str]:
        """Closes/terminates the requested application and verifies termination."""
        app = self.find_app(query)
        if not app:
            logger.warning("Application not found for query: %s", query)
            return False, f"I can't find {query} on this computer."

        if not ProcessManager.is_running(app.process_names):
            logger.info("%s is not currently running.", app.display_name)
            return True, f"{app.display_name} isn't currently running."

        success = ProcessManager.terminate(app.process_names, grace_period=3.0)
        if success:
            return True, f"{app.display_name} has been closed."
        else:
            return False, f"{app.display_name} couldn't be closed."

    def restart_app(self, query: str) -> Tuple[bool, str]:
        """
        Restarts the requested application according to Section 9 specifications:
        1. Detect whether running.
        2. If running: close/terminate, wait for exit, launch, verify, report result.
        3. If not running: report not running, launch, verify, report result.
        4. If fails: report failure. Never falsely report success.
        """
        app = self.find_app(query)
        if not app:
            logger.warning("Application not found for query: %s", query)
            return False, f"I can't find {query} on this computer."

        was_running = ProcessManager.is_running(app.process_names)

        if was_running:
            logger.info("Restarting running application: %s", app.display_name)
            # Terminate running instances
            terminated = ProcessManager.terminate(app.process_names, grace_period=3.5)
            if not terminated:
                logger.error("Failed to terminate %s during restart.", app.display_name)
                return False, f"{app.display_name} couldn't be restarted."

            time.sleep(0.5)

            # Launch again
            launched = ProcessManager.launch(
                launch_command=app.launch_command,
                verify_process_names=app.process_names,
                verify_timeout=6.0,
            )

            if launched:
                logger.info("%s restarted successfully.", app.display_name)
                return True, f"{app.display_name} has been restarted."
            else:
                logger.error("%s failed to start after termination.", app.display_name)
                return False, f"{app.display_name} couldn't be restarted."
        else:
            logger.info("%s is not running. Opening directly.", app.display_name)
            launched = ProcessManager.launch(
                launch_command=app.launch_command,
                verify_process_names=app.process_names,
                verify_timeout=5.0,
            )

            if launched:
                return True, f"{app.display_name} isn't currently running. I'll open it."
            else:
                return False, f"{app.display_name} couldn't be opened."


GLOBAL_APP_MANAGER = ApplicationManager()

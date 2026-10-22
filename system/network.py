"""Network connectivity and browser integration for Alex."""

import os
import shutil
import socket
import subprocess
import urllib.parse
import webbrowser
import winreg
from typing import Optional, Tuple

from storage.logger import logger


def is_connected(timeout: float = 1.5) -> bool:
    """
    Checks whether the PC currently has an active internet connection.
    Tests fast socket connections to reliable, high-availability DNS resolvers.
    """
    test_endpoints = [
        ("8.8.8.8", 53),         # Google Public DNS
        ("1.1.1.1", 53),         # Cloudflare DNS
        ("208.67.222.222", 53),  # OpenDNS
    ]
    for host, port in test_endpoints:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect((host, port))
            sock.close()
            return True
        except OSError:
            continue

    # Secondary fallback check using HTTP head request
    try:
        import requests
        r = requests.head("https://www.google.com", timeout=timeout)
        if r.status_code < 500:
            return True
    except Exception:
        pass

    return False


def find_brave_browser() -> Optional[str]:
    """
    Locates the Brave Browser executable on Windows.
    Scans typical installation directories, Registry App Paths, and PATH.
    """
    # 1. Known default installation paths
    candidate_paths = [
        r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
        r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
    ]
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if local_app_data:
        candidate_paths.append(
            os.path.join(local_app_data, r"BraveSoftware\Brave-Browser\Application\brave.exe")
        )

    for p in candidate_paths:
        if os.path.isfile(p):
            return p

    # 2. Windows Registry App Paths
    for root_key in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        try:
            with winreg.OpenKey(
                root_key, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\brave.exe"
            ) as key:
                val, _ = winreg.QueryValueEx(key, "")
                if val and os.path.isfile(val):
                    return val
        except OSError:
            pass

    # 3. System PATH
    which_path = shutil.which("brave")
    if which_path and os.path.isfile(which_path):
        return which_path

    return None


def open_in_brave(query: str, search_engine: str = "brave") -> Tuple[bool, str]:
    """
    Opens Brave Browser and searches exactly what the user requested.
    Falls back gracefully to the system default browser if Brave is not installed.
    """
    clean_query = query.strip()
    encoded_query = urllib.parse.quote(clean_query)

    if search_engine == "brave":
        search_url = f"https://search.brave.com/search?q={encoded_query}"
    else:
        search_url = f"https://www.google.com/search?q={encoded_query}"

    brave_exe = find_brave_browser()

    if brave_exe and os.path.isfile(brave_exe):
        try:
            logger.info("Opening search in Brave Browser: %s", search_url)
            # Launch asynchronously without blocking
            subprocess.Popen([brave_exe, search_url], shell=False)
            return True, search_url
        except Exception as e:
            logger.error("Failed to launch Brave Browser directly: %s", e)

    # Fallback to system default browser
    try:
        logger.info("Brave not found directly, opening search in default browser: %s", search_url)
        webbrowser.open(search_url)
        return True, search_url
    except Exception as e:
        logger.error("Failed to open browser: %s", e)
        return False, search_url

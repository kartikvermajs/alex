"""Phase 4 Acceptance Test: Real-world Application Control (Open, Close, Restart with process verification)."""

import time
import pytest
from core.command_router import CommandRouter
from system.application_manager import ApplicationManager, GLOBAL_APP_MANAGER
from system.process_manager import ProcessManager


def test_spotify_registry_configuration():
    """Verifies that Spotify is properly configured and auto-detected in the registry."""
    spotify = GLOBAL_APP_MANAGER.find_app("spotify")
    assert spotify is not None
    assert spotify.display_name == "Spotify"
    assert "Spotify.exe" in spotify.process_names


def test_live_notepad_lifecycle_open_restart_close():
    """
    Executes a complete real-world application lifecycle on Windows:
    1. Open Notepad -> verify process exists.
    2. Restart Notepad -> verify termination & relaunch.
    3. Close Notepad -> verify clean exit.
    """
    router = CommandRouter()

    # Step 1: Open Notepad
    open_resp = router.route("Open Notepad")
    assert "Notepad is open" in open_resp or "already open" in open_resp
    assert ProcessManager.is_running(["notepad.exe"]) is True

    # Step 2: Restart Notepad
    restart_resp = router.route("Restart Notepad")
    assert "Notepad has been restarted" in restart_resp
    assert ProcessManager.is_running(["notepad.exe"]) is True

    # Step 3: Close Notepad
    close_resp = router.route("Close Notepad")
    assert "Notepad has been closed" in close_resp
    # Allow small moment for Windows process table update
    time.sleep(0.5)
    assert ProcessManager.is_running(["notepad.exe"]) is False


def test_restart_spotify_routing_and_intent():
    """Verifies routing of natural language variations for restarting Spotify."""
    router = CommandRouter()

    # Verify that variation routes to restart_application
    cmd = router.registry.find_command("restart the Spotify app")
    assert cmd is not None
    assert cmd.name == "restart_application"

    cmd2 = router.registry.find_command("close spotify and open it again")
    assert cmd2 is not None
    assert cmd2.name == "restart_application"

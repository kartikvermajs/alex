"""Unit tests for ApplicationManager and ProcessManager."""

import pytest
from system.application_manager import ApplicationManager, AppInfo


def test_app_registry_lookup():
    manager = ApplicationManager()

    # Spotify lookup
    spotify = manager.find_app("spotify")
    assert spotify is not None
    assert spotify.key == "spotify"
    assert "Spotify.exe" in spotify.process_names

    # Alias lookup
    spotify_alias = manager.find_app("spotify app")
    assert spotify_alias is not None
    assert spotify_alias.key == "spotify"

    # Chrome lookup
    chrome = manager.find_app("chrome")
    assert chrome is not None
    assert chrome.key == "chrome"

    # Unknown app
    unknown = manager.find_app("nonexistent_app_xyz")
    assert unknown is None


def test_open_unknown_app():
    manager = ApplicationManager()
    success, msg = manager.open_app("nonexistent_app_xyz")
    assert success is False
    assert "I can't find" in msg


def test_close_unknown_app():
    manager = ApplicationManager()
    success, msg = manager.close_app("nonexistent_app_xyz")
    assert success is False
    assert "I can't find" in msg


def test_restart_unknown_app():
    manager = ApplicationManager()
    success, msg = manager.restart_app("nonexistent_app_xyz")
    assert success is False
    assert "I can't find" in msg


def test_custom_app_registration():
    manager = ApplicationManager()
    custom_app = AppInfo(
        key="testapp",
        display_name="TestApp",
        process_names=["testapp.exe"],
        launch_command="testapp.exe",
        aliases=["my test tool"],
    )
    manager.register_app(custom_app)

    found = manager.find_app("my test tool")
    assert found is not None
    assert found.key == "testapp"

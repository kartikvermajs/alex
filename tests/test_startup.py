"""Unit tests for Windows Startup configuration."""

from system.startup import (
    is_startup_enabled,
    enable_startup,
    disable_startup,
    toggle_startup,
    get_default_startup_command,
)


def test_get_default_startup_command():
    cmd = get_default_startup_command()
    assert "--tray" in cmd


def test_startup_enable_disable_cycle():
    # Store initial state
    initial = is_startup_enabled()

    # Enable
    res_enable = enable_startup()
    assert res_enable is True
    assert is_startup_enabled() is True

    # Disable
    res_disable = disable_startup()
    assert res_disable is True
    assert is_startup_enabled() is False

    # Restore initial state if it was originally enabled
    if initial:
        enable_startup()

"""Unit tests for Application commands (Open, Close, Restart) and NLU variations."""

import pytest
from commands.applications import (
    OpenApplicationCommand,
    CloseApplicationCommand,
    RestartApplicationCommand,
)
from core.command_router import CommandRouter


def test_open_application_matches_variations():
    cmd = OpenApplicationCommand()
    cases = [
        "Open Spotify",
        "open spotify",
        "Open the Spotify app",
        "Can you open Spotify?",
        "Please open Spotify",
        "launch Spotify",
        "start Spotify",
        "Open Chrome",
        "Open Notepad",
        "Open Calculator",
    ]
    for case in cases:
        assert cmd.matches(case), f"Expected match for: {case}"
        assert cmd._extract_app_name(case) is not None

    negative = [
        "What is the date today?",
        "What time is it?",
        "Restart Spotify",
        "Close Spotify",
    ]
    for case in negative:
        assert not cmd.matches(case), f"Expected no match for: {case}"


def test_close_application_matches_variations():
    cmd = CloseApplicationCommand()
    cases = [
        "Close Spotify",
        "close spotify",
        "Close the Spotify app",
        "Quit Spotify",
        "Exit Spotify",
        "Stop Spotify",
        "Can you close Spotify?",
        "Please close Chrome",
        "Close Notepad",
    ]
    for case in cases:
        assert cmd.matches(case), f"Expected match for: {case}"
        assert cmd._extract_app_name(case) is not None

    negative = [
        "Open Spotify",
        "Restart Spotify",
        "Close Spotify and open it again",  # Restart pattern
    ]
    for case in negative:
        assert not cmd.matches(case), f"Expected no match for: {case}"


def test_restart_application_matches_variations():
    cmd = RestartApplicationCommand()
    cases = [
        "Restart Spotify",
        "restart spotify",
        "Restart the Spotify app",
        "Can you restart Spotify?",
        "Please restart Spotify",
        "Close Spotify and open it again",
        "relaunch Spotify",
        "Restart Chrome",
        "restart notepad",
    ]
    for case in cases:
        assert cmd.matches(case), f"Expected match for: {case}"
        assert cmd._extract_app_name(case) is not None

    negative = [
        "Open Spotify",
        "Close Spotify",
        "What is the date today?",
    ]
    for case in negative:
        assert not cmd.matches(case), f"Expected no match for: {case}"


def test_level_2_system_command_confirmation_flow():
    router = CommandRouter()

    # Step 1: User says "restart my pc"
    prompt = router.route("Restart my PC")
    assert prompt == "Do you want me to restart the computer?"
    assert router.pending_confirmation is not None

    # Step 2: User confirms "Yes"
    confirmed_resp = router.route("Yes")
    assert confirmed_resp == "Restarting the computer."
    assert router.pending_confirmation is None

    # Step 3: Cancellation test
    prompt = router.route("Restart my PC")
    assert prompt == "Do you want me to restart the computer?"
    cancel_resp = router.route("Cancel")
    assert cancel_resp == "Action canceled."
    assert router.pending_confirmation is None

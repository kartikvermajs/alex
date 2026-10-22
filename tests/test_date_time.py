"""Unit tests for Date and Time commands."""

from datetime import datetime
import pytest

from commands.date_time import DateCommand, TimeCommand, get_ordinal_suffix
from core.context import CommandContext


def test_ordinal_suffix():
    assert get_ordinal_suffix(1) == "1st"
    assert get_ordinal_suffix(2) == "2nd"
    assert get_ordinal_suffix(3) == "3rd"
    assert get_ordinal_suffix(4) == "4th"
    assert get_ordinal_suffix(11) == "11th"
    assert get_ordinal_suffix(12) == "12th"
    assert get_ordinal_suffix(13) == "13th"
    assert get_ordinal_suffix(21) == "21st"
    assert get_ordinal_suffix(22) == "22nd"
    assert get_ordinal_suffix(23) == "23rd"
    assert get_ordinal_suffix(31) == "31st"


def test_date_command_matches():
    cmd = DateCommand()
    positive_cases = [
        "What is the date today?",
        "what is the date today",
        "What's today's date?",
        "whats todays date",
        "What date is it?",
        "Tell me today's date",
        "What day is it?",
        "What day is today?",
        "date today",
    ]
    for phrase in positive_cases:
        assert cmd.matches(phrase), f"Expected match for: {phrase}"

    negative_cases = [
        "Restart Spotify",
        "Open Chrome",
        "What is the weather today",
        "Tell me a joke",
    ]
    for phrase in negative_cases:
        assert not cmd.matches(phrase), f"Expected no match for: {phrase}"


def test_date_command_execute():
    cmd = DateCommand()
    context = CommandContext(raw_text="What is the date today?", cleaned_text="what is the date today")
    response = cmd.execute(context)

    now = datetime.now()
    expected_day = now.strftime("%A")
    expected_month = now.strftime("%B")
    expected_ordinal = get_ordinal_suffix(now.day)
    expected_year = str(now.year)

    assert response.startswith("Today is ")
    assert expected_day in response
    assert expected_month in response
    assert expected_ordinal in response
    assert expected_year in response


def test_time_command_matches():
    cmd = TimeCommand()
    positive_cases = [
        "What time is it?",
        "what is the time",
        "What's the time?",
        "Tell me the time",
        "current time",
        "time now",
    ]
    for phrase in positive_cases:
        assert cmd.matches(phrase), f"Expected match for: {phrase}"

    negative_cases = [
        "What is the date today",
        "Restart Spotify",
        "Close Spotify",
    ]
    for phrase in negative_cases:
        assert not cmd.matches(phrase), f"Expected no match for: {phrase}"


def test_time_command_execute():
    cmd = TimeCommand()
    context = CommandContext(raw_text="What time is it?", cleaned_text="what time is it")
    response = cmd.execute(context)

    assert response.startswith("It's ")
    assert ("AM" in response) or ("PM" in response)

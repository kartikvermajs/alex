"""Date and time command handlers."""

from datetime import datetime
import re
from commands.base import Command
from core.context import CommandContext


def get_ordinal_suffix(day: int) -> str:
    """Returns the ordinal representation of a day number (e.g. 1st, 2nd, 22nd)."""
    if 11 <= (day % 100) <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
    return f"{day}{suffix}"


def clean_text_for_matching(text: str) -> str:
    """Cleans punctuation and normalizes contractions for robust pattern matching."""
    # Remove apostrophes so "what's" -> "whats", "today's" -> "todays"
    text = re.sub(r"['’]", "", text.lower())
    # Replace other non-alphanumeric chars with spaces
    cleaned = re.sub(r"[^\w\s]", " ", text)
    return " ".join(cleaned.split())


class DateCommand(Command):
    """Answers queries about today's date."""

    name = "date"
    description = "Reports the current date."
    examples = [
        "what is the date today",
        "what's the date today",
        "what date is it",
        "what is today's date",
        "tell me today's date",
        "what day is today",
        "what day is it",
    ]
    risk_level = 1

    _PATTERNS = [
        r"\b(?:what is|whats|what)\s+(?:the\s+)?date(?:\s+today)?\b",
        r"\b(?:what is|whats|what)\s+(?:the\s+)?day(?:\s+(?:is\s+it|today))?\b",
        r"\b(?:what is|whats|what)\s+today(?:s)?\s+date\b",
        r"\bwhat\s+date\s+is\s+it\b",
        r"\btell\s+me\s+(?:today(?:s)?\s+)?date\b",
        r"\bwhat\s+day\s+is\s+(?:it|today)\b",
        r"\btoday(?:s)?\s+date\b",
        r"\bdate\s+today\b",
    ]

    def matches(self, text: str) -> bool:
        normalized = clean_text_for_matching(text)
        for pattern in self._PATTERNS:
            if re.search(pattern, normalized):
                return True
        return False

    def execute(self, context: CommandContext) -> str:
        now = datetime.now()
        day_name = now.strftime("%A")
        month_name = now.strftime("%B")
        day_ordinal = get_ordinal_suffix(now.day)
        year = now.year
        return f"Today is {day_name}, {month_name} {day_ordinal}, {year}."


class TimeCommand(Command):
    """Answers queries about current time."""

    name = "time"
    description = "Reports the current time."
    examples = [
        "what time is it",
        "what is the time",
        "what's the time",
        "tell me the time",
        "current time",
    ]
    risk_level = 1

    _PATTERNS = [
        r"\b(?:what is|whats|what)\s+(?:the\s+)?time(?:\s+(?:is\s+it|now))?\b",
        r"\b(?:what is|whats|what)\s+time\s+is\s+it\b",
        r"\btell\s+me\s+(?:the\s+)?time\b",
        r"\bcurrent\s+time\b",
        r"\btime\s+now\b",
    ]

    def matches(self, text: str) -> bool:
        normalized = clean_text_for_matching(text)
        for pattern in self._PATTERNS:
            if re.search(pattern, normalized):
                return True
        return False

    def execute(self, context: CommandContext) -> str:
        now = datetime.now()
        time_str = now.strftime("%I:%M %p").lstrip("0")
        return f"It's {time_str}."

"""Context information passed to commands during execution."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict


@dataclass
class CommandContext:
    raw_text: str
    cleaned_text: str
    timestamp: datetime = field(default_factory=datetime.now)
    parameters: Dict[str, Any] = field(default_factory=dict)
    confirmed: bool = False

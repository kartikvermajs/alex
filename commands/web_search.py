"""Web Search Command: Handles explicit and time-sensitive web lookups."""

import re
from typing import Optional, Tuple
from commands.base import Command
from core.context import CommandContext
from storage.logger import logger
from system.network import is_connected, open_in_brave
from system.search_service import SearchService, GLOBAL_SEARCH_SERVICE


class WebSearchCommand(Command):
    """
    Handles explicit search requests ("search for...", "look up...", "browse...", "research...")
    and implicit time-sensitive queries (products, prices, specifications, news, reviews, availability).
    Checks internet connectivity, launches Brave Browser, and produces authoritative summaries with sources.
    """

    name = "web_search"
    description = (
        "Searches the web using Brave Browser, retrieves authoritative summaries, "
        "and speaks the results while verifying internet connection."
    )
    examples = [
        "search for iPhone 16 specifications",
        "search online for cheap flights to Tokyo",
        "look up the price of RTX 5090",
        "browse latest electric vehicles",
        "find best laptops 2026 online",
        "research quantum computing",
        "what is the price of Bitcoin",
        "what are the specifications of PlayStation 5 Pro",
        "tell me the latest news on technology",
        "what are the reviews for Sony WH-1000XM5",
        "is Nintendo Switch 2 available yet",
    ]
    risk_level = 1

    def __init__(self, search_service: SearchService | None = None):
        self.search_service = search_service or GLOBAL_SEARCH_SERVICE

    _EXPLICIT_PATTERNS = [
        r"^(?:alex\s+)?(?:can you\s+)?(?:please\s+)?(?:search\s+for|search\s+online\s+for|search\s+the\s+internet\s+for|search\s+the\s+web\s+for|search)\s+(?:the\s+)?(.+?)(?:\s+online|\s+on\s+the\s+internet|\s+on\s+the\s+web)?$",
        r"^(?:alex\s+)?(?:can you\s+)?(?:please\s+)?(?:look\s+up)\s+(?:the\s+)?(.+?)(?:\s+online|\s+on\s+the\s+internet|\s+on\s+the\s+web)?$",
        r"^(?:alex\s+)?(?:can you\s+)?(?:please\s+)?(?:browse\s+for|browse)\s+(?:the\s+)?(.+?)(?:\s+online|\s+on\s+the\s+internet|\s+on\s+the\s+web)?$",
        r"^(?:alex\s+)?(?:can you\s+)?(?:please\s+)?(?:find\s+information\s+about|find\s+out\s+about|find\s+out|find)\s+(?:the\s+)?(.+?)\s+(?:online|on\s+the\s+internet|on\s+the\s+web)$",
        r"^(?:alex\s+)?(?:can you\s+)?(?:please\s+)?(?:research)\s+(?:the\s+)?(.+?)(?:\s+online|\s+on\s+the\s+internet|\s+on\s+the\s+web)?$",
        r"^(?:alex\s+)?(?:can you\s+)?(?:please\s+)?(?:google)\s+(?:the\s+)?(.+?)$",
    ]

    _TIME_SENSITIVE_PATTERNS = [
        # Prices
        r"^(?:what(?:'s|\s+is)\s+the\s+)?(?:current\s+)?(?:price|cost)\s+of\s+(.+)$",
        r"^how\s+much\s+(?:is|does\s+(.+?)\s+cost)(?:.*)$",
        # Specifications
        r"^(?:what\s+are\s+the\s+|what(?:'s|\s+is)\s+the\s+)?(?:specs|specifications)\s+(?:of|for)\s+(.+)$",
        # News
        r"^(?:what(?:'s|\s+is)\s+the\s+|tell\s+me\s+the\s+)?(?:latest\s+)?news\s+(?:about|on|regarding)\s+(.+)$",
        # Reviews
        r"^(?:what\s+are\s+the\s+|show\s+me\s+)?(?:reviews?|ratings?)\s+(?:of|for)\s+(.+)$",
        # Availability
        r"^is\s+(.+?)\s+(?:available|in\s+stock)(?:\s+yet|\s+now)?$",
        r"^(?:what(?:'s|\s+is)\s+the\s+)?release\s+date\s+(?:of|for)\s+(.+)$",
    ]

    _TIME_SENSITIVE_KEYWORDS = [
        "price of",
        "cost of",
        "specs of",
        "specifications of",
        "specs for",
        "specifications for",
        "latest news",
        "news about",
        "reviews for",
        "review for",
        "reviews of",
        "review of",
        "in stock",
        "available yet",
        "stock price",
        "release date",
    ]

    def _extract_query(self, text: str) -> Optional[Tuple[str, str]]:
        """Extracts search query and categorization ('explicit' or 'time_sensitive')."""
        clean = re.sub(r"[^\w\s\']", " ", text.lower())
        clean = " ".join(clean.split())

        if not clean:
            return None

        # Exclude typical date/time and application triggers
        if clean in ["what time is it", "what is the date", "what is the date today", "what day is it"]:
            return None
        if clean.startswith("restart ") or clean.startswith("open ") or clean.startswith("close "):
            # Check if explicitly asking to search inside
            if not ("search" in clean or "look up" in clean or "browse" in clean):
                return None

        # 1. Explicit search patterns
        for pattern in self._EXPLICIT_PATTERNS:
            match = re.match(pattern, clean)
            if match:
                extracted = match.group(1).strip()
                if extracted:
                    return extracted, "explicit"

        # 2. Time-sensitive patterns
        for pattern in self._TIME_SENSITIVE_PATTERNS:
            match = re.match(pattern, clean)
            if match:
                return clean, "time_sensitive"

        # 3. Time-sensitive keywords
        for kw in self._TIME_SENSITIVE_KEYWORDS:
            if kw in clean:
                return clean, "time_sensitive"

        return None

    def matches(self, text: str) -> bool:
        """Determines if the speech matches an explicit search or time-sensitive request."""
        return self._extract_query(text) is not None

    def execute(self, context: CommandContext) -> str:
        """
        Executes the web search workflow:
        1. Checks internet connection.
        2. If offline, returns "Connect the device to the internet."
        3. If online, opens Brave Browser and searches exactly what was requested.
        4. Queries authoritative sources and summarizes the results.
        5. Formats: "This is what I found on the internet: ..."
        6. Provides sources and links.
        """
        res = self._extract_query(context.raw_text)
        query = res[0] if res else context.raw_text.strip()

        logger.info("Executing web search command for query: \"%s\"", query)

        # Step 1: Check internet connection
        if not is_connected(timeout=1.5):
            logger.warning("Internet connection check failed. System is offline.")
            # Step 2: Speak/return required offline phrase
            return "Connect the device to the internet."

        # Step 3: Open Brave Browser and search exactly what the user requested
        brave_opened, search_url = open_in_brave(query)
        if brave_opened:
            logger.info("Successfully opened Brave search for: \"%s\"", query)

        # Step 4: Use reliable/authoritative sources and summarize relevant results
        search_result = self.search_service.search_and_summarize(query)

        # Step 5 & 6: "This is what I found on the internet." + sources/links
        return search_result["full_text"]

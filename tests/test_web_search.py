"""Unit and acceptance tests for Web Search functionality."""

from unittest.mock import MagicMock, patch
import pytest

from commands.registry import create_default_registry
from commands.web_search import WebSearchCommand
from core.command_router import CommandRouter
from core.context import CommandContext
from system.network import is_connected, find_brave_browser, open_in_brave
from system.search_service import SearchService, clean_html_tags
from voice.text_to_speech import clean_text_for_speech


class TestNetworkIntegration:
    """Verifies network detection and Brave Browser launching."""

    def test_find_brave_browser(self):
        """Finds installed Brave Browser on the system."""
        path = find_brave_browser()
        # Brave is installed on this machine, or returns None if absent
        if path:
            assert "brave" in path.lower()

    def test_is_connected_live(self):
        """Verifies internet check completes quickly."""
        connected = is_connected(timeout=2.0)
        assert isinstance(connected, bool)

    @patch("subprocess.Popen")
    def test_open_in_brave_mocked(self, mock_popen):
        """Verifies query is properly formatted and launched."""
        with patch("system.network.find_brave_browser", return_value=r"C:\fake\brave.exe"), \
             patch("os.path.isfile", return_value=True):
            success, url = open_in_brave("iPhone 16 specs")
            assert success is True
            assert "https://search.brave.com/search?q=iPhone%2016%20specs" in url
            mock_popen.assert_called_once()


class TestSearchService:
    """Verifies search service querying and formatting."""

    def test_clean_html_tags(self):
        text = "<p>This is <b>bold</b> and <i>italic</i>.</p>"
        assert clean_html_tags(text) == "This is bold and italic."

    def test_search_and_summarize_structure(self):
        service = SearchService()
        # Mock external network calls to test synthesis logic deterministically
        with patch.object(
            service,
            "_query_duckduckgo",
            return_value=("Apple announced iPhone 16 with A18 chip and Camera Control.", ("Wikipedia", "https://wiki.org/iphone16")),
        ):
            res = service.search_and_summarize("iPhone 16")
            assert "This is what I found on the internet:" in res["full_text"]
            assert "Apple announced iPhone 16" in res["summary"]
            assert "https://wiki.org/iphone16" in res["full_text"]
            assert "Brave Search" in res["full_text"]
            assert "Source: Wikipedia" in res["speech_text"]


class TestWebSearchCommand:
    """Verifies WebSearchCommand pattern matching, offline behavior, and execution."""

    def setup_method(self):
        self.cmd = WebSearchCommand()

    def test_explicit_search_matches(self):
        explicit_phrases = [
            "search for iPhone 16 specifications",
            "search online for cheap flights to Tokyo",
            "look up the price of RTX 5090",
            "browse latest electric vehicles",
            "find best laptops 2026 online",
            "research quantum computing",
            "google latest weather in Paris",
        ]
        for phrase in explicit_phrases:
            assert self.cmd.matches(phrase), f"Failed to match explicit phrase: {phrase}"

    def test_time_sensitive_matches(self):
        time_sensitive_phrases = [
            "what is the price of Bitcoin",
            "what are the specifications of PlayStation 5 Pro",
            "tell me the latest news on technology",
            "what are the reviews for Sony WH-1000XM5",
            "is Nintendo Switch 2 available yet",
            "what is the release date of GTA 6",
            "how much does a Tesla Model 3 cost",
        ]
        for phrase in time_sensitive_phrases:
            assert self.cmd.matches(phrase), f"Failed to match time-sensitive phrase: {phrase}"

    def test_normal_offline_questions_do_not_match(self):
        offline_phrases = [
            "what is the date today",
            "what time is it",
            "what day is it",
            "open Spotify",
            "restart Chrome",
            "close Spotify",
            "restart my computer",
            "shut down computer",
        ]
        for phrase in offline_phrases:
            assert not self.cmd.matches(phrase), f"Incorrectly matched offline command: {phrase}"

    @patch("commands.web_search.is_connected", return_value=False)
    def test_offline_behavior(self, mock_is_connected):
        """When offline, must respond: 'Connect the device to the internet.'"""
        ctx = CommandContext(raw_text="search for iPhone 16", cleaned_text="search for iphone 16")
        response = self.cmd.execute(ctx)
        assert response == "Connect the device to the internet."

    @patch("commands.web_search.is_connected", return_value=True)
    @patch("commands.web_search.open_in_brave", return_value=(True, "https://search.brave.com"))
    def test_online_behavior_execution(self, mock_brave, mock_conn):
        """When online, opens Brave and returns authoritative summary with sources."""
        mock_service = MagicMock()
        mock_service.search_and_summarize.return_value = {
            "summary": "Nvidia announced the RTX 50 series at CES 2025.",
            "full_text": "This is what I found on the internet:\n\nNvidia announced the RTX 50 series at CES 2025.\n\nSources:\n- [Wikipedia](https://en.wikipedia.org/wiki/GeForce_RTX_50_series)\n- [Brave Search](https://search.brave.com/search?q=RTX%205090)",
            "speech_text": "This is what I found on the internet: Nvidia announced the RTX 50 series at CES 2025. Source: Wikipedia.",
            "sources": [("Wikipedia", "https://en.wikipedia.org/wiki/GeForce_RTX_50_series")],
        }
        cmd = WebSearchCommand(search_service=mock_service)
        ctx = CommandContext(raw_text="search for RTX 5090", cleaned_text="search for rtx 5090")
        response = cmd.execute(ctx)

        assert "This is what I found on the internet:" in response
        assert "Nvidia announced the RTX 50 series" in response
        assert "https://en.wikipedia.org" in response
        mock_brave.assert_called_once()
        mock_service.search_and_summarize.assert_called_once_with("rtx 5090")


class TestCommandRouterIntegration:
    """Verifies end-to-end routing with the full default command registry."""

    def setup_method(self):
        self.registry = create_default_registry()
        self.router = CommandRouter(registry=self.registry)

    def test_routing_date_and_time_remains_offline(self):
        res_date = self.router.route("what is the date today?")
        assert "Today is" in res_date

        res_time = self.router.route("what time is it?")
        assert "It's" in res_time

    def test_routing_applications_remains_offline(self):
        with patch("system.application_manager.ProcessManager.launch", return_value=True), \
             patch("system.application_manager.ProcessManager.is_running", return_value=False):
            res_open = self.router.route("open spotify")
            assert "Spotify is open" in res_open

    @patch("commands.web_search.is_connected", return_value=False)
    def test_routing_search_when_offline(self, mock_conn):
        res = self.router.route("search for cheap mechanical keyboards")
        assert res == "Connect the device to the internet."

    @patch("commands.web_search.is_connected", return_value=True)
    @patch("commands.web_search.open_in_brave", return_value=(True, "https://search.brave.com"))
    def test_routing_time_sensitive_query(self, mock_brave, mock_conn):
        res = self.router.route("what is the price of Bitcoin")
        assert "This is what I found on the internet:" in res


class TestSpeechSanitization:
    """Verifies text-to-speech cleans raw URLs and markdown brackets into natural spoken prose."""

    def test_clean_text_for_speech_markdown_and_urls(self):
        text = (
            "This is what I found on the internet:\n\n"
            "The iPhone 16 features Apple's A18 chip.\n\n"
            "Sources:\n"
            "- [Wikipedia (iPhone 16)](https://en.wikipedia.org/wiki/IPhone_16)\n"
            "- [Brave Search](https://search.brave.com/search?q=iPhone%2016)"
        )
        spoken = clean_text_for_speech(text)
        assert "https://" not in spoken
        assert "[" not in spoken
        assert "]" not in spoken
        assert "This is what I found on the internet: The iPhone 16 features Apple's A18 chip. Sources: Wikipedia (iPhone 16), Brave Search." == spoken

"""Authoritative web search and summarization service for Alex."""

import re
import urllib.parse
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple
import requests

from storage.logger import logger


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json,*/*;q=0.8",
}


def clean_html_tags(text: str) -> str:
    """Removes HTML markup and collapses extra whitespace."""
    cleaned = re.sub(r"<[^>]+>", "", text)
    return " ".join(cleaned.split())


class SearchService:
    """
    Retrieves information from reliable, authoritative sources and produces
    natural, verbal summaries for voice output alongside structured links.
    """

    def __init__(self, timeout: float = 3.5):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)

    def _query_duckduckgo(self, query: str) -> Tuple[Optional[str], Optional[Tuple[str, str]]]:
        """Queries DuckDuckGo Instant Answer API for official facts and abstracts."""
        try:
            url = f"https://api.duckduckgo.com/?q={urllib.parse.quote(query)}&format=json&no_html=1"
            r = self.session.get(url, timeout=self.timeout)
            if r.status_code == 200:
                data = r.json()
                abstract = data.get("AbstractText")
                if abstract:
                    source_name = data.get("AbstractSource") or "DuckDuckGo"
                    source_url = data.get("AbstractURL") or f"https://duckduckgo.com/?q={urllib.parse.quote(query)}"
                    return abstract, (source_name, source_url)
                answer = data.get("Answer")
                if answer:
                    return clean_html_tags(str(answer)), ("DuckDuckGo Instant Answer", "https://duckduckgo.com")
        except Exception as e:
            logger.debug("DuckDuckGo Instant Answer query error: %s", e)
        return None, None

    def _query_wikipedia(self, query: str) -> Tuple[Optional[str], Optional[Tuple[str, str]]]:
        """Queries Wikipedia Search and REST Summary API for authoritative encyclopedic facts."""
        try:
            search_url = (
                f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch="
                f"{urllib.parse.quote(query)}&format=json"
            )
            r = self.session.get(search_url, timeout=self.timeout)
            if r.status_code == 200:
                results = r.json().get("query", {}).get("search", [])
                if results:
                    top_title = results[0]["title"]
                    summary_url = (
                        f"https://en.wikipedia.org/api/rest_v1/page/summary/"
                        f"{urllib.parse.quote(top_title)}"
                    )
                    r_sum = self.session.get(summary_url, timeout=self.timeout)
                    if r_sum.status_code == 200:
                        sum_data = r_sum.json()
                        extract = sum_data.get("extract")
                        if extract:
                            page_url = sum_data.get("content_urls", {}).get("desktop", {}).get(
                                "page", f"https://en.wikipedia.org/wiki/{urllib.parse.quote(top_title)}"
                            )
                            return extract, (f"Wikipedia ({top_title})", page_url)
        except Exception as e:
            logger.debug("Wikipedia search/summary error: %s", e)
        return None, None

    def _query_news_rss(self, query: str) -> Tuple[Optional[str], Optional[Tuple[str, str]]]:
        """Queries Google News RSS for authoritative media reports, current prices, reviews, or availability."""
        try:
            rss_url = (
                f"https://news.google.com/rss/search?q={urllib.parse.quote(query)}"
                f"&hl=en-US&gl=US&ceid=US:en"
            )
            r = self.session.get(rss_url, timeout=self.timeout)
            if r.status_code == 200:
                root = ET.fromstring(r.content)
                items = root.findall(".//item")
                if items:
                    top_item = items[0]
                    title = top_item.find("title").text if top_item.find("title") is not None else ""
                    link = top_item.find("link").text if top_item.find("link") is not None else ""
                    source_name = (
                        top_item.find("source").text if top_item.find("source") is not None else "Google News"
                    )
                    # Clean title if it contains source suffix (e.g. "Title - Source")
                    clean_title = title.rsplit(" - ", 1)[0] if " - " in title else title
                    summary = f"According to {source_name}: {clean_title}."
                    return summary, (source_name, link)
        except Exception as e:
            logger.debug("News RSS query error: %s", e)
        return None, None

    def search_and_summarize(self, query: str) -> Dict[str, any]:
        """
        Executes a multi-tier search across authoritative sources,
        summarizes relevant results, and builds formatted text with links.
        """
        clean_q = query.strip()
        logger.info("Searching authoritative sources for query: \"%s\"", clean_q)

        sources: List[Tuple[str, str]] = []
        primary_summary: Optional[str] = None

        is_news_or_time_sensitive = any(
            k in clean_q.lower()
            for k in ["news", "price", "cost", "review", "rating", "available", "availability", "stock", "release"]
        )

        # 1. If explicitly asking for news, reviews, or prices, check news RSS first
        if is_news_or_time_sensitive:
            summary, src = self._query_news_rss(clean_q)
            if summary:
                primary_summary = summary
                if src:
                    sources.append(src)

        # 2. Try DuckDuckGo Instant Answer
        if not primary_summary:
            summary, src = self._query_duckduckgo(clean_q)
            if summary:
                primary_summary = summary
                if src:
                    sources.append(src)

        # 3. Try Wikipedia
        if not primary_summary:
            summary, src = self._query_wikipedia(clean_q)
            if summary:
                primary_summary = summary
                if src and src not in sources:
                    sources.append(src)

        # 4. If still no summary, try news RSS if we haven't already
        if not primary_summary and not is_news_or_time_sensitive:
            summary, src = self._query_news_rss(clean_q)
            if summary:
                primary_summary = summary
                if src and src not in sources:
                    sources.append(src)

        # Fallback if no specific extract could be parsed
        if not primary_summary:
            primary_summary = f"I found several search results for \"{clean_q}\" in Brave Browser."

        brave_search_url = f"https://search.brave.com/search?q={urllib.parse.quote(clean_q)}"
        sources.append(("Brave Search", brave_search_url))

        # Trim summary to 2-3 sentences for natural, concise speech
        sentences = re.split(r"(?<=[.!?])\s+", primary_summary.strip())
        concise_summary = " ".join(sentences[:3]).strip()

        # Build full text response for logs / UI
        sources_lines = "\n".join([f"- [{name}]({url})" for name, url in sources[:3]])
        full_text = (
            f"This is what I found on the internet:\n\n"
            f"{concise_summary}\n\n"
            f"Sources:\n{sources_lines}"
        )

        # Build verbal response for speech
        primary_source_name = sources[0][0] if sources else "the web"
        speech_text = (
            f"This is what I found on the internet: {concise_summary} "
            f"Source: {primary_source_name}."
        )

        return {
            "summary": concise_summary,
            "full_text": full_text,
            "speech_text": speech_text,
            "sources": sources,
            "brave_url": brave_search_url,
        }


# Global search service instance
GLOBAL_SEARCH_SERVICE = SearchService()

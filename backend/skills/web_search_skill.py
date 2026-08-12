"""
Lightweight web search skill using DuckDuckGo's HTML endpoint — no API
key required. Good enough for quick factual lookups; swap in a proper
search API (Brave, Serper, Bing) for production use.
"""
from __future__ import annotations

import logging

import requests
from bs4 import BeautifulSoup  # noqa: F401  (kept optional; see note below)

from skills.base_skill import BaseSkill

logger = logging.getLogger("jarvis.skills.web_search")


class WebSearchSkill(BaseSkill):
    name = "web_search"
    description = "Search the web for current information and return the top results."
    parameters = {
        "query": {"type": "string", "description": "Search query", "required": True},
    }

    async def run(self, query: str) -> str:
        try:
            resp = requests.get(
                "https://html.duckduckgo.com/html/",
                params={"q": query},
                headers={"User-Agent": "Mozilla/5.0 (JarvisAssistant/1.0)"},
                timeout=8,
            )
            resp.raise_for_status()
        except requests.exceptions.RequestException as exc:
            logger.warning("Web search failed: %s", exc)
            return "I couldn't reach the web search service right now."

        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(resp.text, "html.parser")
            results = []
            for result in soup.select(".result__body")[:3]:
                title_el = result.select_one(".result__a")
                snippet_el = result.select_one(".result__snippet")
                if title_el:
                    title = title_el.get_text(strip=True)
                    snippet = snippet_el.get_text(strip=True) if snippet_el else ""
                    results.append(f"{title} — {snippet}")
            if not results:
                return f"No results found for '{query}'."
            return "Top results:\n" + "\n".join(f"- {r}" for r in results)
        except Exception as exc:
            logger.warning("Failed to parse search results: %s", exc)
            return "I got a response but couldn't parse the search results."

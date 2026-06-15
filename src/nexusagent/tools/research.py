"""Research and web fetching tools for NexusAgent.

Provides web search (Exa/Tavily), local documentation search (ctx7),
and URL fetching with HTML-to-text conversion. All functions are
standalone (no class required) and use httpx for HTTP requests.
"""

import logging
import os
import subprocess
from html.parser import HTMLParser

import httpx

logger = logging.getLogger(__name__)


class _HTMLToText(HTMLParser):
    """Simple HTML to text converter (no external dependencies)."""

    def __init__(self):
        super().__init__()
        self._result: list[str] = []
        self._skip = False
        self._skip_tags = {"script", "style", "head"}
        self._current_tags: list[str] = []

    def handle_starttag(self, tag, attrs):
        self._current_tags.append(tag)
        if tag in self._skip_tags:
            self._skip = True
        elif tag in ("br",):
            self._result.append("\n")
        elif tag in ("p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "tr"):
            if self._result and not self._result[-1].endswith("\n"):
                self._result.append("\n")
        elif tag in ("td", "th"):
            self._result.append(" ")

    def handle_endtag(self, tag):
        if self._current_tags and self._current_tags[-1] == tag:
            self._current_tags.pop()
        if tag in self._skip_tags:
            self._skip = False
        elif tag in ("p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "tr", "blockquote") and self._result and not self._result[-1].endswith("\n"):
                self._result.append("\n")

    def handle_data(self, data):
        if not self._skip:
            self._result.append(data)

    def get_text(self) -> str:
        text = "".join(self._result)
        # Collapse excessive whitespace
        import re
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()


def _html_to_markdown(html: str) -> str:
    """Convert HTML to plain text (markdown-like). No external dependencies."""
    parser = _HTMLToText()
    try:
        parser.feed(html)
    except Exception:
        # Fallback: strip tags with regex
        import re
        text = re.sub(r"<[^>]+>", "", html)
        return text.strip()
    return parser.get_text()


def _search_exa(query: str) -> str | None:
    """Search using Exa API."""
    api_key = os.environ.get("EXA_API_KEY")
    if not api_key:
        logger.debug("EXA_API_KEY not set")
        return None

    try:
        from exa_py import Exa  # type: ignore[import-untyped]

        client = Exa(api_key=api_key)
        # Use the newer search() API (search_and_contents is deprecated)
        response = client.search(query, num_results=5, text=True)
        results = response.results
        if not results:
            return f"No results for: {query}"
        parts = []
        for r in results:
            title = getattr(r, "title", "Untitled")
            url = getattr(r, "url", "")
            text = getattr(r, "text", "")[:600]
            parts.append(f"Title: {title}\nURL: {url}\n{text}")
        return "\n\n".join(parts)
    except ImportError:
        logger.debug("exa_py not installed")
        return None
    except Exception as e:
        logger.warning(f"Exa search failed: {e}")
        return None


def _search_tavily(query: str) -> str | None:
    """Search using Tavily API as fallback."""
    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        logger.debug("TAVILY_API_KEY not set")
        return None

    try:
        from tavily import TavilyClient  # type: ignore[import-untyped]

        client = TavilyClient(api_key=api_key)
        response = client.search(query, max_results=3)
        results = response.get("results", [])
        if not results:
            return f"No results for: {query}"
        parts = []
        for r in results:
            parts.append(
                f"Title: {r.get('title', 'N/A')}\nURL: {r.get('url', 'N/A')}\n{r.get('content', '')[:500]}"
            )
        return "\n\n".join(parts)
    except ImportError:
        logger.debug("tavily not installed")
        return None
    except Exception as e:
        logger.warning(f"Tavily search failed: {e}")
        return None


def search_web(query: str) -> str:
    """
    Web search with Exa primary and Tavily fallback.
    Requires EXA_API_KEY and/or TAVILY_API_KEY in environment.
    """
    # Try Exa first
    result = _search_exa(query)
    if result:
        return result

    # Fallback to Tavily
    result = _search_tavily(query)
    if result:
        return result

    # Both failed or unavailable
    missing = []
    if not os.environ.get("EXA_API_KEY"):
        missing.append("EXA_API_KEY")
    if not os.environ.get("TAVILY_API_KEY"):
        missing.append("TAVILY_API_KEY")
    if missing:
        return f"Search unavailable — missing env vars: {', '.join(missing)}"
    return "Search unavailable — no search SDKs installed (exa-py or tavily)"


def search_local_docs(query: str) -> str:
    """
    Search local documentation using ctx7 via subprocess.
    """
    try:
        result = subprocess.run(
            ["npx", "ctx7@latest", "docs", "query", query],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error searching docs: {e.stderr}"


def fetch_url(url: str) -> str:
    """
    Fetch a URL and return the content as markdown-formatted text.

    Uses httpx for fetching and a built-in HTML-to-text converter.
    Truncates output to 5000 chars max.
    """
    max_chars = 5000
    try:
        response = httpx.get(url, follow_redirects=True, timeout=15.0)
        response.raise_for_status()
    except httpx.TimeoutException:
        return f"Error: Request to {url} timed out"
    except httpx.HTTPStatusError as e:
        return f"Error: HTTP {e.response.status_code} for {url}"
    except httpx.RequestError as e:
        return f"Error: Could not fetch {url}: {e}"

    content_type = response.headers.get("content-type", "")
    if "application/json" in content_type:
        import json
        try:
            data = response.json()
            text = json.dumps(data, indent=2, default=str)
        except Exception:
            text = response.text
    elif "text/html" in content_type:
        text = _html_to_markdown(response.text)
    else:
        # Plain text or unknown — return as-is
        text = response.text

    # Truncate
    if len(text) > max_chars:
        text = text[:max_chars] + f"\n\n[truncated — {len(text):,} total chars]"

    return text

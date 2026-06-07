import logging
import os
import subprocess

logger = logging.getLogger(__name__)


def _search_exa(query: str) -> str | None:
    """Search using Exa API."""
    api_key = os.environ.get("EXA_API_KEY")
    if not api_key:
        logger.debug("EXA_API_KEY not set")
        return None

    try:
        from exa_py import Exa  # type: ignore[import-untyped]

        client = Exa(api_key=api_key)
        response = client.search_and_contents(query, num_results=3, text=True)
        results = response.results
        if not results:
            return f"No results for: {query}"
        parts = []
        for r in results:
            parts.append(f"Title: {r.title}\nURL: {r.url}\n{r.text[:500]}")
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

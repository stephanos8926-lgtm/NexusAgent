import subprocess


# Note: Assumes EXA_API_KEY is available in the environment
def search_web(query: str) -> str:
    """
    Placeholder for web search using Exa.
    In a real implementation, this would use an 'exa-py' client or similar.
    """
    # For now, return a placeholder as the environment may not have the SDK installed.
    return f"Web search results for: {query}"

def search_local_docs(query: str) -> str:
    """
    Search local documentation using ctx7 via subprocess.
    """
    try:
        # Based on GEMINI.md instructions for ctx7:
        # Step 3: Fetch docs: `npx ctx7@latest docs <libraryId> "<user's question>"`
        # This implementation simplifies the process to a single call as requested.
        result = subprocess.run(
            ["npx", "ctx7@latest", "docs", "query", query],
            capture_output=True, text=True, check=True
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error searching docs: {e.stderr}"

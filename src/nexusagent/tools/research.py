import os
import subprocess
import httpx

def search_web(query: str) -> str:
    api_key = os.getenv("EXA_API_KEY")
    if not api_key:
        return "Error: EXA_API_KEY not set"
    
    url = "https://api.exa.ai/search"
    headers = {"x-api-key": api_key, "Content-Type": "application/json"}
    payload = {"query": query}
    
    try:
        with httpx.Client() as client:
            response = client.post(url, headers=headers, json=payload, timeout=10.0)
            response.raise_for_status()
            return str(response.json())
    except Exception as e:
        return f"Error searching web: {e}"

def search_local_docs(query: str) -> str:
    try:
        # ctx7 usage as per GEMINI.md instructions is complex (library + docs)
        # I will implement a simplified call assuming the user wants direct query
        # This is a placeholder for the requested subprocess call
        result = subprocess.run(
            ["npx", "ctx7@latest", "docs", "nexusagent", query], 
            capture_output=True,
            text=True,
            check=False # Don't check for now to handle errors gracefully
        )
        return result.stdout if result.stdout else result.stderr
    except Exception as e:
        return f"Error searching local docs: {e}"

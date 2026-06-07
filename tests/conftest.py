import os
from pathlib import Path

# Load .env from project root so API keys are available for all tests
# Use override=False so test-specific env vars take precedence
try:
    from dotenv import load_dotenv  # type: ignore[import-untyped]
    _env = Path(__file__).parent.parent / ".env"
    if _env.exists():
        load_dotenv(_env, override=False)
except ImportError:
    pass

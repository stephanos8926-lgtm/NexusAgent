"""NexusAgent — production entrypoint.

Delegates to the Click CLI in ``nexusagent.cli``.  Supports::

    python -m nexusagent          # interactive client
    python -m nexusagent server   # start API server
    python -m nexusagent run "task"
"""

import sys

from nexusagent.cli import main

if __name__ == "__main__":
    main()

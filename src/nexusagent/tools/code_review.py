"""Code review tool — compat shim.

This file re-exports from the code_review/ subpackage for backward compatibility.
New code should import directly from nexusagent.tools.code_review.
"""

from nexusagent.tools.code_review import *  # noqa: F401, F402

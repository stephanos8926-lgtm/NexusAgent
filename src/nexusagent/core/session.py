"""Session manager  compat shim.

Re-exports from the session/ subpackage for backward compatibility.
"""

from nexusagent.core.session import (  # noqa: F401
    Session,
    SessionManager,
    get_session_manager,
    session_manager,
    set_session_manager,
)

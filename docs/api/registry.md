# Registry

The tool registry manages tool metadata, policy enforcement, and discovery.

## Core Functions

::: nexusagent.tools.registry
    options:
      show_source: false
      show_root_heading: false
      members:
        - register_tool
        - tool_search
        - auto_correct
        - get_manifest
        - set_policy_context
        - get_policy_context
        - _is_tool_allowed
        - ROLE_MANIFESTS

## Discovery

::: nexusagent.tools.discovery
    options:
      show_source: false
      members:
        - validate_tool_call

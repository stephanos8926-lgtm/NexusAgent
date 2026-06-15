import uuid

import gradio as gr

from nexusagent.server.sdk import NexusSDK

# Aesthetic Constants (Industrial/Utilitarian Direction)
THEME_COLOR = "#FF4B2B"  # Industrial Orange-Red
BG_COLOR = "#1A1A1A"  # Deep Charcoal
TEXT_COLOR = "#E0E0E0"  # Soft White


async def handle_submit(text: str, sdk: NexusSDK | None = None) -> tuple[str, str]:
    """Submit a task via the SDK. Returns (log_message, status)."""
    if sdk is None:
        sdk = NexusSDK()

    if not text:
        return "Error: Task definition empty", "ERROR"

    task_id = str(uuid.uuid4())[:8]

    try:
        await sdk.submit_task(
            {
                "id": task_id,
                "description": text,
            }
        )
        return f"[{task_id}] Submitted successfully", "ACTIVE"
    except Exception as e:
        return f"[{task_id}] Submission failed: {e}", "ERROR"


def create_ui():
    with gr.Blocks(
        title="NexusAgent Control Center",
        css=f"""
        .gradio-container {{ background-color: {BG_COLOR}; color: {TEXT_COLOR}; font-family: 'JetBrains Mono', monospace; }}
        .task-card {{ border: 1px solid {THEME_COLOR}; border-radius: 0px; padding: 10px; margin-bottom: 10px; }}
        .submit-btn {{ background-color: {THEME_COLOR} !important; color: white !important; border-radius: 0px !important; font-weight: bold !important; text-transform: uppercase !important; }}
        .status-badge {{ font-size: 0.8em; padding: 2px 5px; border: 1px solid {TEXT_COLOR}; }}
    """,
    ) as demo:
        gr.Markdown("""
        # ⚡ NEXUSAGENT CONTROL CENTER
        **System Status:** `ONLINE` | **Protocol:** `CONTRACT-FIRST`
        """)

        with gr.Row():
            with gr.Column(scale=2):
                task_input = gr.Textbox(
                    label="TASK DEFINITION",
                    placeholder="Enter coding objective...",
                    lines=3,
                    container=False,
                )
                submit_btn = gr.Button(
                    "TRANSMIT TASK", variant="primary", elem_classes=["submit-btn"]
                )

            with gr.Column(scale=1):
                status_box = gr.Textbox(label="SDK STATUS", value="IDLE", interactive=False)

        with gr.Row():
            output_log = gr.TextArea(
                label="SYSTEM OUTPUT",
                placeholder="Awaiting transmission...",
                interactive=False,
                lines=10,
                elem_classes=["task-card"],
            )

        submit_btn.click(
            fn=handle_submit,
            inputs=[task_input],
            outputs=[output_log, status_box],
        )

    return demo


def run_ui() -> None:
    """Entry point for the nexus-web command."""
    import os
    demo = create_ui()
    # SECURITY: bind to localhost by default, require token auth
    demo.launch(
        server_name=os.getenv("NEXUS_WEB_HOST", "127.0.0.1"),
        server_port=int(os.getenv("NEXUS_WEB_PORT", "7860")),
        auth=_check_web_auth if os.getenv("NEXUS_WEB_AUTH", "1") == "1" else None,
        auth_message="Enter the Nexus Agent API key",
    )


def _check_web_auth(username: str, password: str) -> bool:
    """Check web UI auth against the configured API key."""
    import os
    # Use the API key from environment or config as the password
    # Username is ignored — only the password (API key) is checked
    api_key = os.getenv("NEXUS_API_KEY", "")
    if not api_key:
        # If no API key configured, check against auth manager
        try:
            from nexusagent.infrastructure.auth import get_auth_manager
            stored = get_auth_manager().get_key("api")
            if stored is None:
                return False  # No key configured, deny
            api_key = stored
        except Exception:
            return False
    import hmac
    return hmac.compare_digest(password, api_key)


if __name__ == "__main__":
    run_ui()

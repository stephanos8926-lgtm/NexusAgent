import uuid

import gradio as gr

from nexusagent.models import TaskSchema
from nexusagent.sdk import NexusSDK

# Aesthetic Constants (Industrial/Utilitarian Direction)
THEME_COLOR = "#FF4B2B"  # Industrial Orange-Red
BG_COLOR = "#1A1A1A"     # Deep Charcoal
TEXT_COLOR = "#E0E0E0"   # Soft White

def handle_submit(text, sdk=None):
    if sdk is None:
        from nexusagent.sdk import NexusSDK
        sdk = NexusSDK()

    if not text:
        return "Error: Task definition empty", "ERROR"

    task_id = str(uuid.uuid4())[:8]
    task = TaskSchema(id=task_id, description=text)

    result = sdk.submit_task(task)

    if result.success:
        return f"[{task_id}] {result.data}", "ACTIVE"
    else:
        return f"Critical Failure: {result.error}", "ERROR"

def create_ui():
    sdk = NexusSDK()

    with gr.Blocks(title="NexusAgent Control Center", css=f"""
        .gradio-container {{ background-color: {BG_COLOR}; color: {TEXT_COLOR}; font-family: 'JetBrains Mono', monospace; }}
        .task-card {{ border: 1px solid {THEME_COLOR}; border-radius: 0px; padding: 10px; margin-bottom: 10px; }}
        .submit-btn {{ background-color: {THEME_COLOR} !important; color: white !important; border-radius: 0px !important; font-weight: bold !important; text-transform: uppercase !important; }}
        .status-badge {{ font-size: 0.8em; padding: 2px 5px; border: 1px solid {TEXT_COLOR}; }}
    """) as demo:

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
                    container=False
                )
                submit_btn = gr.Button("TRANSMIT TASK", variant="primary", elem_classes=["submit-btn"])

            with gr.Column(scale=1):
                status_box = gr.Textbox(label="SDK STATUS", value="IDLE", interactive=False)

        with gr.Row():
            output_log = gr.TextArea(
                label="SYSTEM OUTPUT",
                placeholder="Awaiting transmission...",
                interactive=False,
                lines=10,
                elem_classes=["task-card"]
            )

        submit_btn.click(
            fn=lambda t: handle_submit(t),
            inputs=[task_input],
            outputs=[output_log, status_box]
        )

    return demo

if __name__ == "__main__":
    demo = create_ui()
    demo.launch(server_name="0.0.0.0", server_port=7860)

"""
Main entry point for Hugging Face Spaces and Gradio deployment.
"""
from app.gradio_app import create_ui

demo = create_ui()

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)

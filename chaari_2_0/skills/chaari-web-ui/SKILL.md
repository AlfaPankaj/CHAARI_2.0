---
name: chaari-web-ui
description: "Launch a Gradio-based web interface for CHAARI 2.0. This skill provides a modern dashboard for interacting with Chaari's brain, memory, and status systems."
---

# 🤖 CHAARI 2.0 Web Dashboard Skill

This skill allows you to transform your terminal-based Chaari into a beautiful web interface.

## Quick Start

1.  **Ensure Requirements**: You must have `gradio` installed:
    ```bash
    pip install gradio
    ```
2.  **Launch the UI**:
    Execute the Python script located in the `scripts/` folder:
    ```bash
    python skills/chaari-web-ui/scripts/gradio_app.py
    ```

## Features

- **Real-time Chat**: Connects directly to Chaari's Llama 3.2 (Ollama) or Groq backend.
- **Streaming Output**: Tokens appear instantly as they are generated.
- **Live Status Dashboard**: Monitors your Groq API limits and user profile.
- **VRAM Optimized**: Shared memory with the existing Chaari architecture.

## Folder Structure

- `scripts/gradio_app.py`: The core Gradio application wrapper.
- `SKILL.md`: This documentation.

---

*Note: This skill is part of the CHAARI 2.0 Power Architecture.*

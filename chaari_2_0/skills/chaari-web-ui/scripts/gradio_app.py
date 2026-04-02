import os                                                                                                                  
import sys                                                                                                                 
import gradio as gr                                                                                                        
import threading                                                                                                          
import time                                                                                                                                                                                                                                      
# Ensure project root is in path                                                                                           
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))          
9                                                                                                                            
from core.brain import Brain                                                                                               
from core.memory import Memory                                                                                            
# Global state                                                                                                             
memory = Memory()                                                                                                          
memory.start_session()                                                                                                     
brain = Brain(memory=memory)                                                                                               

def chaari_chat(message, history):
    """Chat function for Gradio."""
    response = ""
    for chunk in brain.chat_stream(message):
        response += chunk
        yield response

def get_system_status():
    """Fetch status for the dashboard."""
    status = brain.groq.get_status()
    user_name = memory.get_user_name() or "Boss"

    html = f"""
    <div style='padding: 20px; border-radius: 10px; background-color: #1e1e1e; color: white;'>
        <h3>System Status</h3>
        <p><b>User:</b> {user_name}</p>
        <p><b>Model:</b> {brain.model}</p>
        <p><b>LLM Backend:</b> {'Groq (Cloud)' if status['available'] else 'Ollama (Local)'}</p>
        <p><b>Requests Left:</b> {status['today_remaining']}</p>
    </div>
    """
    return html

# Build UI
with gr.Blocks(theme=gr.themes.Soft()) as demo:
    gr.Markdown("# 🤖 CHAARI 2.0 — Web Dashboard")
    with gr.Row():
        with gr.Column(scale=3):
            chatbot = gr.ChatInterface(
                fn=chaari_chat,
                title="Chat with Chaari",
                description="Your Personal AI Operating Companion",
            )
        with gr.Column(scale=1):
            status_box = gr.HTML(get_system_status())
            refresh_btn = gr.Button("Refresh Status")
            refresh_btn.click(get_system_status, outputs=status_box)

if __name__ == "__main__":
    demo.launch(share=False)
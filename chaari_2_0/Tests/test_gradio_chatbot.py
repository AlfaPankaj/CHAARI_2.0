import gradio as gr
import sys

print(f"Gradio version: {gr.__version__}")

try:
    c = gr.Chatbot(type="messages")
    print("SUCCESS: Chatbot accepts type='messages'")
    has_type = True
except TypeError as e:
    print(f"FAILURE: Chatbot does NOT accept type='messages'. Error: {e}")
    has_type = False

c = gr.Chatbot()
messages_data = [{"role": "user", "content": "hi"}]
tuples_data = [["hi", "hello"]]

print("\nTesting data formats on gr.Chatbot().postprocess():")

try:
    c.postprocess(messages_data)
    print("SUCCESS: Accepts messages format (dictionaries)")
except Exception as e:
    print(f"FAILURE: Does NOT accept messages format. Error: {e}")

try:
    c.postprocess(tuples_data)
    print("SUCCESS: Accepts tuples format ([[user, bot], ...])")
except Exception as e:
    print(f"FAILURE: Does NOT accept tuples format. Error: {e}")

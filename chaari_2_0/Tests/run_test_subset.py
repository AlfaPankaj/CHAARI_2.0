
import sys
import os
import re

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.brain import Brain
from core.memory import Memory
from core.os_executor import OSExecutor

def run_range(start=0, end=20):
    memory = Memory()
    memory.start_session()
    brain = Brain(memory=memory)
    brain.inject_executor(OSExecutor())
    
    suite_file = "C:\\Users\\PANKAJ\\OneDrive\\Documents\\project\\CHAARI 2.0\\Master_Test_Suite.md"
    if not os.path.exists(suite_file):
        print(f"File not found: {suite_file}")
        return

    with open(suite_file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    commands = []
    for line in lines:
        match = re.search(r'- \[ \] "(.*?)"', line)
        if match:
            commands.append(match.group(1))

    print(f"Total commands: {len(commands)}. Running {start} to {end}...")
    
    for i in range(start, min(end, len(commands))):
        cmd = commands[i]
        print(f"\n--- Test {i+1} ---")
        print(f"You: {cmd}")
        response = brain.chat(cmd)
        print(f"Chaari: {response}")
        brain.clear_history()

if __name__ == "__main__":
    start = 0
    end = 20
    if len(sys.argv) > 1:
        start = int(sys.argv[1])
    if len(sys.argv) > 2:
        end = int(sys.argv[2])
    run_range(start, end)

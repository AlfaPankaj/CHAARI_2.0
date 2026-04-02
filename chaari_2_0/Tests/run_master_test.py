
import sys
import os
import re
import time
import subprocess
from statistics import mean

def run_master_test():
    # 1. Parse Test Suite
    suite_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Master_Test_Suite.md")
    if not os.path.exists(suite_path):
        suite_path = "Master_Test_Suite.md"
        if not os.path.exists(suite_path):
            print(f"Error: Master_Test_Suite.md not found.")
            return

    with open(suite_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Split by Levels
    level_sections = re.split(r'## (\d+\. Level \d+: .*?)\n', content)
    level_data = []
    for i in range(1, len(level_sections), 2):
        name = level_sections[i]
        cmd_block = level_sections[i+1]
        cmds = re.findall(r'- \[ \] "(.*?)"', cmd_block)
        if cmds:
            level_data.append({"name": name, "commands": cmds})

    # 2. Start Chaari as a Subprocess
    # We use -u for unbuffered binary stdout to ensure we catch the prompt instantly
    cmd_args = ['py', '-3.10', '-u', 'chaari_2_0/main.py', '--live']
    
    print("="*65)
    print("  CHAARI 2.0 - MASTER STRESS TEST (RUNNING THROUGH MAIN.PY)")
    print("="*65)
    print(f"  Starting subprocess: {' '.join(cmd_args)}")
    
    # Use subprocess with pipes for interactive automation
    process = subprocess.Popen(
        cmd_args,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding='utf-8',
        bufsize=1
    )

    results = {}

    def wait_for_prompt():
        """Reads output character by character until 'You: ' prompt is detected."""
        buffer = ""
        while True:
            char = process.stdout.read(1)
            if not char:
                break
            buffer += char
            if buffer.endswith("You: "):
                break
        return buffer

    print("  [System] Waiting for Chaari boot sequence...")
    wait_for_prompt() # Consume initial boot log
    print("  [System] Chaari is ready. Starting tests.\n")

    try:
        for level in level_data:
            lname = level["name"]
            cmds = level["commands"]
            print(f"\n>>> {lname}")
            results[lname] = []
            
            for cmd in cmds:
                print(f"  Testing: \"{cmd}\"")
                
                start_time = time.time()
                
                # Send command to Chaari's stdin
                process.stdin.write(cmd + "\n")
                process.stdin.flush()
                
                # Wait for Chaari to finish and show next prompt
                response_block = wait_for_prompt()
                
                end_time = time.time()
                elapsed = end_time - start_time
                results[lname].append(elapsed)
                
                # Extract clean response from the output block
                # Usually looking for "Chaari: [text] \n You: "
                match = re.search(r'Chaari: (.*?)\n?\s*You: ', response_block, re.DOTALL)
                if match:
                    response_text = match.group(1).strip()
                else:
                    # Fallback if regex fails
                    response_text = response_block.replace("You: ", "").replace("Chaari: ", "").strip()
                
                print(f"  Output: {response_text}")
                print(f"  Time: {elapsed:.2f}s\n")
                
    except KeyboardInterrupt:
        print("\n\n  [System] Test suite stopped by user.")
    finally:
        process.terminate()

    # Final Summary Table
    print("\n" + "="*65)
    print("  PER-LEVEL PERFORMANCE SUMMARY")
    print("="*65)
    print(f"  {'Level Name':<45} | {'Avg Time (s)':<15}")
    print("  " + "-" * 62)
    
    total_avg_list = []
    for lname, times in results.items():
        if times:
            avg = mean(times)
            total_avg_list.append(avg)
            print(f"  {lname[:45]:<45} | {avg:<15.2f}")
    
    if total_avg_list:
        print("  " + "-" * 62)
        print(f"  {'OVERALL SYSTEM AVERAGE':<45} | {mean(total_avg_list):<15.2f}")
    print("="*65)

if __name__ == "__main__":
    run_master_test()

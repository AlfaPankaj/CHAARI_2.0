
import sys
import os
from unittest.mock import MagicMock, patch

# Add current dir to path
sys.path.append(os.getcwd())

from core.brain import Brain
from core.executor_port import ExecutionResult, ExecutionStatus

def test_master_flow():
    print("\n=== STARTING MASTER FLOW TEST ===")
    
    # 1. Initialize Brain with real components where possible
    brain = Brain()
    
    # Mock only external/expensive components
    brain.groq = MagicMock()
    brain.command_registry = MagicMock()
    
    # SETUP MOCK DATA
    user_input = "create a log.txt and how much RAM am I using"
    mock_ram_data = "Memory: 4.2GB used, 16GB total"
    
    # Mock Tool Detection (Problem 3)
    # Simulate that tools detects RAM request
    brain.tools.detect_tool_intent = MagicMock(return_value={
        "tool": "system_stats",
        "real": True,
        "data": mock_ram_data
    })
    
    # Mock OS Execution (Problem 2)
    mock_exec_result = ExecutionResult(
        status=ExecutionStatus.SUCCESS,
        intent="create_file",
        output="Created file: log.txt",
        duration_ms=50
    )
    brain.command_registry.execute = MagicMock(return_value=mock_exec_result)
    
    # Mock intent context extraction to avoid complex regex logic in test
    brain._extract_params = MagicMock(return_value={"file_path": "log.txt"})
    
    # 2. RUN PRE-PROCESS
    print(f"Step 1: Processing user input: '{user_input}'")
    stop, processed_input, tool_ctx, note, direct_resp = brain._pre_process(user_input)
    
    # VERIFY PROBLEM 2 & 3 STATE
    print(f"Step 2: Checking State Injection...")
    print(f"  [RECEIPT]: {brain._last_execution_receipt}")
    print(f"  [TRUTH]: {brain._last_system_truth}")
    
    assert "create_file" in brain._last_execution_receipt.lower()
    assert "4.2GB" in brain._last_system_truth
    
    # 3. VERIFY MESSAGE BUILDING
    print(f"Step 3: Verifying LLM Prompt Construction...")
    messages = brain._build_messages(processed_input, tool_ctx, note)
    system_prompt = messages[0]["content"]
    
    # Ensure receipts are in the system prompt for the LLM
    assert "[ACTION RECEIPT]" in system_prompt
    assert "[VERIFIED SYSTEM DATA]" in system_prompt
    assert mock_ram_data in system_prompt
    
    print("✅ Receipt and Truth successfully injected into System Prompt!")
    
    # 4. SIMULATE LLM RESPONSE (Problem 2 - Personality Synthesis)
    brain.groq.chat.return_value = "Boss, aapki 4.2GB RAM use ho rahi hai, aur maine log.txt bhi bana di hai!"
    
    print(f"Step 4: LLM generating personality-driven response...")
    response = brain.chat(user_input)
    print(f"  [CHAARI]: {response}")
    
    # 5. VERIFY CLEANUP
    print(f"Step 5: Verifying context cleanup...")
    assert brain._last_execution_receipt == ""
    assert brain._last_system_truth == ""
    print("✅ Context cleared successfully after turn.")
    
    print("\n=== MASTER FLOW TEST PASSED! ===")

if __name__ == "__main__":
    try:
        test_master_flow()
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

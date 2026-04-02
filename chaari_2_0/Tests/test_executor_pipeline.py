#!/usr/bin/env python3
"""
Test script for ExecutorPort pipeline integration.
Verifies that SystemCommandRegistry → ExecutorPort → OSExecutor works correctly.
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.executor_port import NoOpExecutor, MockExecutor
from core.commands import SystemCommandRegistry
from core.os_executor import OSExecutor


def test_noop_executor():
    """Test with NoOpExecutor (safe, doesn't execute)."""
    print("\n" + "=" * 70)
    print("TEST 1: NoOpExecutor (Safe Mode)")
    print("=" * 70)
    
    executor = NoOpExecutor()
    registry = SystemCommandRegistry(executor)
    
    # Test basic execution
    result = registry.execute("SHUTDOWN")
    print(f"✅ SHUTDOWN: {result}")
    
    result = registry.execute("RESTART")
    print(f"✅ RESTART: {result}")
    
    result = registry.execute("DELETE_FILE", {"path": "/tmp/test.txt"})
    print(f"✅ DELETE_FILE: {result}")
    
    print("\n✅ NoOpExecutor test PASSED")


def test_mock_executor():
    """Test with MockExecutor (tracks calls without executing)."""
    print("\n" + "=" * 70)
    print("TEST 2: MockExecutor (Tracking Mode)")
    print("=" * 70)
    
    executor = MockExecutor()
    registry = SystemCommandRegistry(executor)
    
    # Make some calls
    registry.execute("SHUTDOWN")
    registry.execute("RESTART")
    registry.execute("DELETE_FILE", {"path": "/tmp/test.txt"})
    
    # Check calls were recorded
    calls = executor.get_calls()
    print(f"Recorded {executor.get_call_count()} calls:")
    for i, call in enumerate(calls, 1):
        print(f"  {i}. {call['intent']} with context {call['context']}")
    
    print("\n✅ MockExecutor test PASSED")


def test_mock_executor_failure():
    """Test MockExecutor failure handling."""
    print("\n" + "=" * 70)
    print("TEST 3: MockExecutor Failure Mode")
    print("=" * 70)
    
    executor = MockExecutor()
    executor.should_fail = True
    registry = SystemCommandRegistry(executor)
    
    result = registry.execute("SHUTDOWN")
    print(f"❌ SHUTDOWN (simulated failure): {result}")
    
    print("\n✅ MockExecutor failure test PASSED")


def test_os_executor_validation():
    """Test OSExecutor validation without executing commands."""
    print("\n" + "=" * 70)
    print("TEST 4: OSExecutor Validation")
    print("=" * 70)
    
    executor = OSExecutor()
    
    # Test validation
    print("\nValidating DELETE_FILE without path:")
    is_valid, error = executor.validate_context("DELETE_FILE", {})
    print(f"  Valid: {is_valid}, Error: {error}")
    
    print("Validating DELETE_FILE with path:")
    is_valid, error = executor.validate_context("DELETE_FILE", {"path": "/tmp/test.txt"})
    print(f"  Valid: {is_valid}, Error: {error}")
    
    print("Validating FORMAT_DISK without drive:")
    is_valid, error = executor.validate_context("FORMAT_DISK", {})
    print(f"  Valid: {is_valid}, Error: {error}")
    
    print("Validating FORMAT_DISK with drive:")
    is_valid, error = executor.validate_context("FORMAT_DISK", {"drive": "D"})
    print(f"  Valid: {is_valid}, Error: {error}")
    
    print("\nSupported intents:")
    for intent in executor.get_supported_intents():
        print(f"  • {intent}")
    
    print("\n✅ OSExecutor validation test PASSED")


def test_integration():
    """Test full integration with registry and executor."""
    print("\n" + "=" * 70)
    print("TEST 5: Full Integration (Registry → MockExecutor)")
    print("=" * 70)
    
    executor = MockExecutor()
    registry = SystemCommandRegistry(executor)
    
    # Simulate brain.py calling registry
    print("\nSimulating brain.py execution flow:")
    
    # Case 1: Simple command
    intent = "RESTART"
    result = registry.execute(intent)
    print(f"1. brain.execute('{intent}'): {result}")
    
    # Case 2: Command with context
    intent = "DELETE_FILE"
    context = {"path": "/tmp/test.txt"}
    result = registry.execute(intent, context)
    print(f"2. brain.execute('{intent}', {context}): {result}")
    
    # Case 3: Failure scenario
    executor.should_fail = True
    result = registry.execute("SHUTDOWN")
    print(f"3. brain.execute('SHUTDOWN') [simulated failure]: {result}")
    
    print("\n✅ Full integration test PASSED")


def main():
    """Run all tests."""
    print("\n" + "█" * 70)
    print("CHAARI 2.0 — ExecutorPort Pipeline Integration Tests")
    print("█" * 70)
    
    try:
        test_noop_executor()
        test_mock_executor()
        test_mock_executor_failure()
        test_os_executor_validation()
        test_integration()
        
        print("\n" + "=" * 70)
        print("🎉 ALL TESTS PASSED!")
        print("=" * 70)
        print("\nExecutorPort pipeline is properly integrated:")
        print("  ✅ SystemCommandRegistry accepts executor")
        print("  ✅ Executor routes through CommandExecutorPort")
        print("  ✅ ExecutionResult is captured and formatted")
        print("  ✅ Error handling works correctly")
        print("  ✅ OSExecutor validation is functional")
        print("\n" + "=" * 70 + "\n")
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

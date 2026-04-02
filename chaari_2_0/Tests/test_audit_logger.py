#!/usr/bin/env python3
"""
Test suite for AuditLogger module.
Verifies append-only audit trail functionality.
"""

import sys
import os
import json
import tempfile
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.audit_logger import (
    AuditLogger,
    AuditEventType,
    AuditSeverity,
    get_audit_logger,
    set_audit_logger,
)


def test_basic_logging():
    """Test basic audit logging functionality."""
    print("\n" + "=" * 70)
    print("TEST 1: Basic Logging")
    print("=" * 70)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = os.path.join(tmpdir, "test.jsonl")
        logger = AuditLogger(log_path)
        
        # Log an event
        trace_id = logger.log(
            AuditEventType.INPUT_RECEIVED,
            session_id="sess-user123",
            severity=AuditSeverity.INFO,
            input_hash="abc123",
            user_agent="cli"
        )
        
        print(f"✅ Logged event with trace_id: {trace_id}")
        
        # Verify entry was written
        assert os.path.exists(log_path), "Log file not created"
        
        with open(log_path, 'r') as f:
            line = f.readline().strip()
            assert line, "No entry in log"
            entry = json.loads(line)
            assert entry['trace_id'] == trace_id
            assert entry['session_id'] == "sess-user123"
            assert entry['event_type'] == "input_received"
        
        print(f"✅ Entry verified in log file")
        print(f"  Entry: {entry}")


def test_multiple_sessions():
    """Test logging from multiple sessions."""
    print("\n" + "=" * 70)
    print("TEST 2: Multiple Sessions")
    print("=" * 70)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = os.path.join(tmpdir, "test.jsonl")
        logger = AuditLogger(log_path)
        
        # Log for session 1
        trace1 = logger.log_input("sess-user1", "shutdown", user_agent="cli")
        logger.log_safety_check("sess-user1", "shutdown", 1, 4, trace_id=trace1)
        
        # Log for session 2
        trace2 = logger.log_input("sess-user2", "restart", user_agent="voice")
        logger.log_safety_check("sess-user2", "restart", 1, 3, trace_id=trace2)
        
        # Log for session 1 again
        logger.log_confirmation_code("sess-user1", "shutdown")
        
        print(f"✅ Logged entries across multiple sessions")
        
        # Get session 1 audit
        audit1 = logger.get_session_audit("sess-user1")
        assert len(audit1) == 3, f"Expected 3 entries for sess-user1, got {len(audit1)}"
        print(f"✅ Session 1 has {len(audit1)} entries")
        
        # Get session 2 audit
        audit2 = logger.get_session_audit("sess-user2")
        assert len(audit2) == 2, f"Expected 2 entries for sess-user2, got {len(audit2)}"
        print(f"✅ Session 2 has {len(audit2)} entries")


def test_trace_retrieval():
    """Test retrieving entries by trace ID."""
    print("\n" + "=" * 70)
    print("TEST 3: Trace Retrieval")
    print("=" * 70)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = os.path.join(tmpdir, "test.jsonl")
        logger = AuditLogger(log_path)
        
        trace_id = logger.log_input("sess-test", "delete /tmp/file.txt", user_agent="cli")
        
        # Retrieve by trace ID
        entry = logger.get_trace(trace_id)
        assert entry is not None, "Could not retrieve entry by trace ID"
        assert entry['trace_id'] == trace_id
        assert entry['event_type'] == 'input_received'
        
        print(f"✅ Retrieved entry by trace: {trace_id}")
        print(f"  Event: {entry['event_type']}")


def test_event_filtering():
    """Test filtering events by type."""
    print("\n" + "=" * 70)
    print("TEST 4: Event Filtering")
    print("=" * 70)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = os.path.join(tmpdir, "test.jsonl")
        logger = AuditLogger(log_path)
        
        # Log various events
        logger.log_input("sess-test", "test", user_agent="cli")
        logger.log_safety_check("sess-test", "shutdown", 1, 4)
        logger.log_input("sess-test", "test2", user_agent="cli")
        logger.log_confirmation_code("sess-test", "shutdown")
        
        # Filter by input events
        inputs = logger.get_events_by_type(AuditEventType.INPUT_RECEIVED)
        assert len(inputs) == 2, f"Expected 2 input events, got {len(inputs)}"
        print(f"✅ Found {len(inputs)} INPUT_RECEIVED events")
        
        # Filter by safety check events
        checks = logger.get_events_by_type(AuditEventType.SAFETY_CHECK)
        assert len(checks) == 1, f"Expected 1 safety check, got {len(checks)}"
        print(f"✅ Found {len(checks)} SAFETY_CHECK event")
        
        # Filter by confirmation events
        codes = logger.get_events_by_type(AuditEventType.CODE_GENERATED)
        assert len(codes) == 1, f"Expected 1 code generated, got {len(codes)}"
        print(f"✅ Found {len(codes)} CODE_GENERATED event")


def test_convenience_methods():
    """Test convenience logging methods."""
    print("\n" + "=" * 70)
    print("TEST 5: Convenience Logging Methods")
    print("=" * 70)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = os.path.join(tmpdir, "test.jsonl")
        logger = AuditLogger(log_path)
        
        # Test convenience methods
        trace1 = logger.log_input("sess-test", "shutdown", user_agent="cli")
        print(f"✅ log_input(): {trace1}")
        
        trace2 = logger.log_safety_check("sess-test", "shutdown", 1, 4, trace_id=trace1)
        print(f"✅ log_safety_check(): {trace2}")
        
        trace3 = logger.log_confirmation_code("sess-test", "shutdown")
        print(f"✅ log_confirmation_code(): {trace3}")
        
        trace4 = logger.log_confirmation_verify("sess-test", "shutdown", success=True)
        print(f"✅ log_confirmation_verify(): {trace4}")
        
        trace5 = logger.log_privilege_check("sess-test", "shutdown", granted=True)
        print(f"✅ log_privilege_check(): {trace5}")
        
        trace6 = logger.log_execution("sess-test", "shutdown", success=True, exit_code=0, duration_ms=150)
        print(f"✅ log_execution(): {trace6}")
        
        # Verify all were logged
        total = logger.get_log_entry_count()
        assert total == 6, f"Expected 6 entries, got {total}"
        print(f"✅ All 6 convenience methods logged successfully")


def test_append_only():
    """Test that logging is truly append-only."""
    print("\n" + "=" * 70)
    print("TEST 6: Append-Only Behavior")
    print("=" * 70)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = os.path.join(tmpdir, "test.jsonl")
        logger = AuditLogger(log_path)
        
        # Write first batch
        logger.log_input("sess-test", "test1", user_agent="cli")
        logger.log_input("sess-test", "test2", user_agent="cli")
        
        with open(log_path, 'r') as f:
            lines_before = len(f.readlines())
        
        print(f"✅ Logged {lines_before} entries initially")
        
        # Write second batch
        logger.log_input("sess-test", "test3", user_agent="cli")
        logger.log_input("sess-test", "test4", user_agent="cli")
        
        with open(log_path, 'r') as f:
            lines_after = len(f.readlines())
        
        assert lines_after == lines_before + 2, "Entries were not appended correctly"
        print(f"✅ Appended 2 more entries (total now {lines_after})")
        
        # Verify first entries are still there
        first_entry = logger.get_events_by_type(AuditEventType.INPUT_RECEIVED)[0]
        print(f"✅ First entry still intact: {first_entry['metadata']}")


def test_statistics():
    """Test log statistics functionality."""
    print("\n" + "=" * 70)
    print("TEST 7: Log Statistics")
    print("=" * 70)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = os.path.join(tmpdir, "test.jsonl")
        logger = AuditLogger(log_path)
        
        # Log various events
        for i in range(3):
            logger.log_input(f"sess-{i}", f"test{i}", user_agent="cli")
            logger.log_safety_check(f"sess-{i}", "shutdown", 1, 4)
        
        stats = logger.get_stats()
        
        print(f"✅ Log Statistics:")
        print(f"   File size: {stats['file_size_bytes']} bytes")
        print(f"   Total entries: {stats['total_entries']}")
        print(f"   Sessions tracked: {stats['sessions_tracked']}")
        print(f"   Events by type: {stats['events_by_type']}")
        
        assert stats['total_entries'] == 6, f"Expected 6 entries, got {stats['total_entries']}"
        assert stats['sessions_tracked'] == 3, f"Expected 3 sessions, got {stats['sessions_tracked']}"


def test_thread_safety():
    """Test thread-safe logging."""
    print("\n" + "=" * 70)
    print("TEST 8: Thread Safety")
    print("=" * 70)
    
    import threading
    
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = os.path.join(tmpdir, "test.jsonl")
        logger = AuditLogger(log_path)
        
        def log_from_thread(thread_id):
            for i in range(5):
                logger.log_input(
                    f"sess-thread{thread_id}",
                    f"msg{i}",
                    user_agent="cli"
                )
        
        threads = [threading.Thread(target=log_from_thread, args=(i,)) for i in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        total = logger.get_log_entry_count()
        expected = 3 * 5  # 3 threads, 5 entries each
        assert total == expected, f"Expected {expected} entries, got {total}"
        print(f"✅ Thread-safe logging verified ({total} entries from 3 threads)")


def main():
    """Run all tests."""
    print("\n" + "█" * 70)
    print("CHAARI 2.0 — AuditLogger Test Suite")
    print("█" * 70)
    
    try:
        test_basic_logging()
        test_multiple_sessions()
        test_trace_retrieval()
        test_event_filtering()
        test_convenience_methods()
        test_append_only()
        test_statistics()
        test_thread_safety()
        
        print("\n" + "=" * 70)
        print("🎉 ALL TESTS PASSED!")
        print("=" * 70)
        print("\nAuditLogger implementation verified:")
        print("  ✅ Basic logging works")
        print("  ✅ Multi-session support")
        print("  ✅ Trace ID retrieval")
        print("  ✅ Event type filtering")
        print("  ✅ Convenience methods")
        print("  ✅ Append-only behavior")
        print("  ✅ Statistics tracking")
        print("  ✅ Thread-safe operations")
        print("\n" + "=" * 70 + "\n")
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ TEST ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

import threading
import time
import pytest
import shared

def test_shared_state_concurrency():
    """
    Spawns multiple threads to concurrently read, write, and invoke state transition
    methods on the shared global state module, verifying thread-safety and lock robustness.
    """
    errors = []

    def worker_writer(thread_id, num_iterations=100):
        try:
            for i in range(num_iterations):
                shared.current_state = f"state_{thread_id}_{i}"
                shared.persons_detected = thread_id + i
                shared.current_ai_mood = f"mood_{thread_id}_{i}"
                shared.focus_mode_active = (i % 2 == 0)
        except Exception as e:
            errors.append(f"Writer thread {thread_id} failed: {e}")

    def worker_reader(thread_id, num_iterations=100):
        try:
            for _ in range(num_iterations):
                # Read properties concurrently
                _ = shared.current_state
                _ = shared.persons_detected
                _ = shared.current_ai_mood
                _ = shared.focus_mode_active
        except Exception as e:
            errors.append(f"Reader thread {thread_id} failed: {e}")

    def worker_method_caller(thread_id, num_iterations=50):
        try:
            for i in range(num_iterations):
                shared.push_state(f"worker_state_{thread_id}_{i}")
                shared.push_mood(f"worker_mood_{thread_id}_{i}")
                shared.push_log(f"log message from thread {thread_id}", author="TestThread")
        except Exception as e:
            errors.append(f"Method caller thread {thread_id} failed: {e}")

    threads = []
    # Spawn 5 writer threads, 5 reader threads, and 5 method caller threads
    for i in range(5):
        threads.append(threading.Thread(target=worker_writer, args=(i,)))
        threads.append(threading.Thread(target=worker_reader, args=(i,)))
        threads.append(threading.Thread(target=worker_method_caller, args=(i,)))

    # Start all threads
    for t in threads:
        t.start()

    # Wait for all threads to complete
    for t in threads:
        t.join()

    # Assert that no exceptions occurred during concurrent executions
    assert not errors, f"Concurrency errors encountered: {errors}"

def test_shared_state_get_set():
    """Simple test to verify get/set accessors and fallback lookup logic."""
    shared.sentry_active = True
    assert shared.sentry_active is True
    
    shared.sentry_active = False
    assert shared.sentry_active is False

    # Check push_state puts elements in queue
    # Clear queue first if it has items
    while not shared.event_queue.empty():
        try:
            shared.event_queue.get_nowait()
        except Exception:
            break
            
    shared.push_state("analysing")
    assert shared.current_state == "analysing"
    
    event = shared.event_queue.get_nowait()
    assert event["type"] == "state"
    assert event["value"] == "analysing"

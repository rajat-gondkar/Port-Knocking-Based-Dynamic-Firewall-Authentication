"""
Unit tests for server.sequence_tracker
Run: python tests/test_sequence_tracker.py
"""
import sys
import time
sys.path.insert(0, '/Users/rajat.gondkar/Desktop/NPS Project')

from server.sequence_tracker import SequenceTracker


def test_basic_sequence():
    st = SequenceTracker([7000, 8000, 9000], timeout=10)
    assert st.record_knock("192.168.1.1", 7000) == False
    assert st.record_knock("192.168.1.1", 8000) == False
    assert st.record_knock("192.168.1.1", 9000) == True
    print("[PASS] test_basic_sequence")


def test_wrong_first_knock():
    st = SequenceTracker([7000, 8000, 9000], timeout=10)
    assert st.record_knock("192.168.1.2", 9999) == False
    assert st.get_progress("192.168.1.2") == "0/3"
    print("[PASS] test_wrong_first_knock")


def test_wrong_mid_sequence_reset():
    st = SequenceTracker([7000, 8000, 9000], timeout=10)
    st.record_knock("192.168.1.3", 7000)
    assert st.record_knock("192.168.1.3", 9999) == False
    assert st.get_progress("192.168.1.3") == "0/3"
    print("[PASS] test_wrong_mid_sequence_reset")


def test_timeout_reset():
    st = SequenceTracker([7000, 8000, 9000], timeout=1)
    st.record_knock("192.168.1.4", 7000)
    time.sleep(1.5)
    assert st.record_knock("192.168.1.4", 8000) == False
    assert st.get_progress("192.168.1.4") == "0/3"
    print("[PASS] test_timeout_reset")


def test_multiple_ips():
    st = SequenceTracker([7000, 8000, 9000], timeout=10)
    st.record_knock("10.0.0.1", 7000)
    st.record_knock("10.0.0.2", 7000)
    st.record_knock("10.0.0.2", 8000)
    assert st.get_progress("10.0.0.1") == "1/3"
    assert st.get_progress("10.0.0.2") == "2/3"
    print("[PASS] test_multiple_ips")


def test_reset_method():
    st = SequenceTracker([7000, 8000, 9000], timeout=10)
    st.record_knock("192.168.1.5", 7000)
    st.reset("192.168.1.5")
    assert st.get_progress("192.168.1.5") == "0/3"
    print("[PASS] test_reset_method")


def test_progress_reporting():
    st = SequenceTracker([7000, 8000, 9000], timeout=10)
    assert st.get_progress("1.2.3.4") == "0/3"
    st.record_knock("1.2.3.4", 7000)
    assert st.get_progress("1.2.3.4") == "1/3"
    st.record_knock("1.2.3.4", 8000)
    assert st.get_progress("1.2.3.4") == "2/3"
    print("[PASS] test_progress_reporting")


if __name__ == "__main__":
    test_basic_sequence()
    test_wrong_first_knock()
    test_wrong_mid_sequence_reset()
    test_timeout_reset()
    test_multiple_ips()
    test_reset_method()
    test_progress_reporting()
    print("\n[OK] All sequence_tracker tests passed!")

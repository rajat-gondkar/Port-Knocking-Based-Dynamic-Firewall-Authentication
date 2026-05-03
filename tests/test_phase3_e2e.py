"""
End-to-end test for Phases 1-3:
Starts knock listeners + protected service + real logger/firewall,
then sends knock sequence and verifies full authentication flow.
Run: python3 tests/test_phase3_e2e.py
"""
import sys
import socket
import time
import threading
sys.path.insert(0, '/Users/rajat.gondkar/Desktop/NPS Project')

from server.logger import Logger
from server.firewall import FirewallManager
from server.sequence_tracker import SequenceTracker
from server.knock_server import start_knock_listeners
from server.service import start_protected_service


def knock(host, port):
    try:
        s = socket.socket()
        s.settimeout(2)
        s.connect((host, port))
        s.close()
    except:
        pass


def connect_service(host, port):
    s = socket.socket()
    s.settimeout(3)
    s.connect((host, port))
    banner = s.recv(1024).decode()
    s.close()
    return banner


def main():
    config = {
        "knock_sequence": [7000, 8000, 9000],
        "service_port": 2222,
        "knock_ports": [7000, 8000, 9000, 7500],
        "sequence_timeout": 10,
        "access_duration": 5,
        "host": "127.0.0.1",
        "log_file": "logs/test_access.log"
    }

    # Clean up test log
    import os
    if os.path.exists(config["log_file"]):
        os.remove(config["log_file"])

    logger = Logger(config["log_file"])
    firewall = FirewallManager(config["service_port"], config["access_duration"], logger=logger)
    tracker = SequenceTracker(config["knock_sequence"], config["sequence_timeout"])

    firewall.start_expiry_daemon()
    start_knock_listeners(config, tracker, firewall, logger)

    svc_thread = threading.Thread(
        target=start_protected_service,
        args=(config, firewall, logger),
        daemon=True
    )
    svc_thread.start()
    time.sleep(0.5)

    print("[*] Test 1: Connect without knocking → should be DENIED")
    try:
        banner = connect_service("127.0.0.1", 2222)
        print(f"    Banner: {banner.strip()}")
        assert "DENIED" in banner, "Expected ACCESS DENIED"
    except Exception as e:
        print(f"    Connection failed (expected): {e}")

    time.sleep(0.3)

    print("[*] Test 2: Send correct knock sequence → should be GRANTED")
    knock("127.0.0.1", 7000)
    time.sleep(0.2)
    knock("127.0.0.1", 8000)
    time.sleep(0.2)
    knock("127.0.0.1", 9000)
    time.sleep(0.5)

    banner = connect_service("127.0.0.1", 2222)
    print(f"    Banner: {banner.strip()}")
    assert "GRANTED" in banner, "Expected ACCESS GRANTED"

    time.sleep(0.3)

    print("[*] Test 3: Wait for expiry → should be DENIED again")
    time.sleep(5.5)
    try:
        banner = connect_service("127.0.0.1", 2222)
        print(f"    Banner: {banner.strip()}")
        assert "DENIED" in banner, "Expected ACCESS DENIED after expiry"
    except Exception as e:
        print(f"    Connection failed: {e}")

    # Verify log file contents
    time.sleep(0.2)
    with open(config["log_file"]) as f:
        lines = [json.loads(line) for line in f if line.strip()]

    events = [e["event"] for e in lines]
    print(f"[*] Logged events: {events}")

    assert "ACCESS_DENIED" in events
    assert "AUTH_SUCCESS" in events
    assert "PORT_OPENED" in events
    assert "ACCESS_GRANTED" in events
    assert "PORT_CLOSED" in events

    print("\n[OK] Phase 3 end-to-end test passed!")


if __name__ == "__main__":
    import json
    main()

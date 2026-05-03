"""
Integration smoke test for knock_server.py + sequence_tracker.py
Starts listeners, sends knocks, verifies behavior.
"""
import sys
import socket
import time
import threading
sys.path.insert(0, '/Users/rajat.gondkar/Desktop/NPS Project')

from server.sequence_tracker import SequenceTracker
from server.knock_server import start_knock_listeners


class FakeFirewall:
    def __init__(self):
        self.opened = []
    def open_port(self, ip):
        self.opened.append(ip)
    def start_expiry_daemon(self):
        pass


class FakeLogger:
    def __init__(self):
        self.events = []
    def log(self, event_type, ip, port=None, message=""):
        self.events.append((event_type, ip, port, message))
    def get_recent(self, n=50):
        return []


def knock(host, port):
    try:
        s = socket.socket()
        s.settimeout(2)
        s.connect((host, port))
        s.close()
    except:
        pass


def main():
    config = {
        "knock_sequence": [7000, 8000, 9000],
        "knock_ports": [7000, 8000, 9000, 7500],
        "host": "127.0.0.1",
        "sequence_timeout": 10,
    }

    tracker = SequenceTracker(config["knock_sequence"], config["sequence_timeout"])
    firewall = FakeFirewall()
    logger = FakeLogger()

    start_knock_listeners(config, tracker, firewall, logger)
    time.sleep(0.5)  # Let threads start

    print("[*] Sending correct sequence...")
    knock("127.0.0.1", 7000)
    time.sleep(0.2)
    knock("127.0.0.1", 8000)
    time.sleep(0.2)
    knock("127.0.0.1", 9000)
    time.sleep(0.5)

    print(f"[*] FakeFirewall.opened: {firewall.opened}")
    auth_success = any(e[0] == "AUTH_SUCCESS" for e in logger.events)
    print(f"[*] AUTH_SUCCESS logged: {auth_success}")
    assert "127.0.0.1" in firewall.opened, "Expected IP to be authenticated"
    assert auth_success, "Expected AUTH_SUCCESS event"

    print("[*] Sending wrong sequence...")
    knock("127.0.0.1", 7000)
    time.sleep(0.2)
    knock("127.0.0.1", 7500)  # wrong — monitored but breaks sequence
    time.sleep(0.5)

    auth_fail = any(e[0] == "AUTH_FAIL" for e in logger.events)
    print(f"[*] AUTH_FAIL logged: {auth_fail}")
    assert auth_fail, "Expected AUTH_FAIL event"

    print("\n[OK] Knock server smoke test passed!")


if __name__ == "__main__":
    main()

"""
Unit & smoke tests for Phase 2: firewall.py + service.py
Run: python3 tests/test_phase2.py
"""
import sys
import socket
import time
import threading
sys.path.insert(0, '/Users/rajat.gondkar/Desktop/NPS Project')

from server.firewall import FirewallManager
from server.service import start_protected_service


class FakeLogger:
    def __init__(self):
        self.events = []
    def log(self, event_type, ip, port=None, message=""):
        self.events.append((event_type, ip, port, message))
    def get_recent(self, n=50):
        return []


def test_firewall_basic():
    print("[*] Testing FirewallManager basics...")
    fw = FirewallManager(service_port=2222, access_duration=2, logger=None)
    assert not fw.is_allowed("1.2.3.4")
    fw.open_port("1.2.3.4")
    assert fw.is_allowed("1.2.3.4")
    time.sleep(2.5)
    assert not fw.is_allowed("1.2.3.4")
    print("[PASS] test_firewall_basic")


def test_firewall_sessions():
    print("[*] Testing FirewallManager sessions...")
    logger = FakeLogger()
    fw = FirewallManager(service_port=2222, access_duration=5, logger=logger)
    fw.open_port("10.0.0.1")
    fw.open_port("10.0.0.2")
    sessions = fw.get_active_sessions()
    assert len(sessions) == 2
    ips = {s["ip"] for s in sessions}
    assert ips == {"10.0.0.1", "10.0.0.2"}
    for s in sessions:
        assert 0 < s["remaining_seconds"] <= 5
    print("[PASS] test_firewall_sessions")


def test_firewall_close_port():
    print("[*] Testing FirewallManager manual close...")
    fw = FirewallManager(service_port=2222, access_duration=30, logger=None)
    fw.open_port("192.168.1.1")
    assert fw.is_allowed("192.168.1.1")
    fw.close_port("192.168.1.1")
    assert not fw.is_allowed("192.168.1.1")
    print("[PASS] test_firewall_close_port")


def test_firewall_expiry_daemon():
    print("[*] Testing FirewallManager expiry daemon...")
    logger = FakeLogger()
    fw = FirewallManager(service_port=2222, access_duration=1, logger=logger)
    fw.start_expiry_daemon()
    fw.open_port("172.16.0.1")
    assert fw.is_allowed("172.16.0.1")
    time.sleep(2.5)
    # Daemon should have pruned it by now
    sessions = fw.get_active_sessions()
    assert len(sessions) == 0
    assert not fw.is_allowed("172.16.0.1")
    fw.stop_expiry_daemon()
    print("[PASS] test_firewall_expiry_daemon")


def test_protected_service():
    print("[*] Testing protected service (gated TCP echo)...")
    logger = FakeLogger()
    fw = FirewallManager(service_port=2222, access_duration=5, logger=logger)
    fw.open_port("127.0.0.1")

    config = {"host": "127.0.0.1", "service_port": 2222}
    t = threading.Thread(target=start_protected_service, args=(config, fw, logger), daemon=True)
    t.start()
    time.sleep(0.3)

    # Allowed connection
    s = socket.socket()
    s.settimeout(3)
    s.connect(("127.0.0.1", 2222))
    banner = s.recv(1024).decode()
    assert "ACCESS GRANTED" in banner, f"Unexpected banner: {banner}"
    s.sendall(b"hello\n")
    echo = s.recv(1024).decode()
    assert echo == "hello\n", f"Unexpected echo: {echo}"
    s.close()

    # Denied connection (different IP simulation — use actual remote connection not possible locally)
    # Instead, close the port and try again from same IP
    fw.close_port("127.0.0.1")
    s2 = socket.socket()
    s2.settimeout(3)
    s2.connect(("127.0.0.1", 2222))
    banner2 = s2.recv(1024).decode()
    assert "ACCESS DENIED" in banner2, f"Unexpected banner: {banner2}"
    s2.close()

    assert any(e[0] == "ACCESS_GRANTED" for e in logger.events)
    assert any(e[0] == "ACCESS_DENIED" for e in logger.events)
    print("[PASS] test_protected_service")


if __name__ == "__main__":
    test_firewall_basic()
    test_firewall_sessions()
    test_firewall_close_port()
    test_firewall_expiry_daemon()
    test_protected_service()
    print("\n[OK] All Phase 2 tests passed!")

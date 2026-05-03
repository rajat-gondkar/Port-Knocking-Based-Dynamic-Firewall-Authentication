"""
Full integration test for Phase 6: main.py wiring
Run: python3 tests/test_phase6_integration.py
"""
import sys
import os
import json
import socket
import time
import threading
import urllib.request
sys.path.insert(0, '/Users/rajat.gondkar/Desktop/NPS Project')

from server.logger import Logger
from server.firewall import FirewallManager
from server.sequence_tracker import SequenceTracker
from server.knock_server import start_knock_listeners
from server.service import start_protected_service
from server.api_server import start_api_server


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


def api_get(path):
    url = f"http://127.0.0.1:8080{path}"
    with urllib.request.urlopen(url, timeout=3) as resp:
        return json.loads(resp.read().decode())


def api_post(path, data):
    url = f"http://127.0.0.1:8080{path}"
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode(),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=3) as resp:
        return json.loads(resp.read().decode())


def main():
    config = {
        "knock_sequence": [7000, 8000, 9000],
        "service_port": 2222,
        "knock_ports": [7000, 8000, 9000, 7500, 8500],
        "sequence_timeout": 10,
        "access_duration": 5,
        "host": "127.0.0.1",
        "api_host": "127.0.0.1",
        "api_port": 8080,
        "log_file": "logs/integration_test.log"
    }

    if os.path.exists(config["log_file"]):
        os.remove(config["log_file"])

    logger = Logger(config["log_file"])
    firewall = FirewallManager(config["service_port"], config["access_duration"], logger=logger)
    tracker = SequenceTracker(config["knock_sequence"], config["sequence_timeout"])

    firewall.start_expiry_daemon()
    start_knock_listeners(config, tracker, firewall, logger)

    svc_thread = threading.Thread(target=start_protected_service, args=(config, firewall, logger), daemon=True)
    svc_thread.start()

    api_thread = threading.Thread(target=start_api_server, args=(config, firewall, logger, tracker), daemon=True)
    api_thread.start()

    time.sleep(0.6)

    print("[*] Test A: Dashboard loads")
    status = api_get("/api/status")
    assert status["sequence"] == [7000, 8000, 9000]
    print(f"    -> Sequence: {status['sequence']}, Service: {status['service_port']}")

    print("[*] Test B: Knock client simulation via API")
    api_post("/api/knock", {"host": "127.0.0.1", "sequence": [7000, 8000, 9000], "delay": 0.3})
    time.sleep(0.5)

    sessions = api_get("/api/sessions")
    assert len(sessions["sessions"]) >= 1, "Expected at least 1 active session after knock"
    print(f"    -> Active sessions: {len(sessions['sessions'])}")

    print("[*] Test C: Service access granted")
    banner = connect_service("127.0.0.1", 2222)
    assert "GRANTED" in banner, f"Expected ACCESS GRANTED, got: {banner}"
    print(f"    -> Banner: {banner.strip()}")

    print("[*] Test D: Logs show full event chain")
    logs = api_get("/api/logs?n=20")
    events = [e["event"] for e in logs["logs"]]
    print(f"    -> Events: {events}")
    assert "KNOCK_ATTEMPT" in events
    assert "AUTH_SUCCESS" in events
    assert "PORT_OPENED" in events
    assert "ACCESS_GRANTED" in events

    print("[*] Test E: Revoke via dashboard API")
    session_ip = sessions["sessions"][0]["ip"]
    api_post("/api/revoke", {"ip": session_ip})
    time.sleep(0.3)
    sessions_after = api_get("/api/sessions")
    assert len(sessions_after["sessions"]) == 0, "Expected no sessions after revoke"
    print(f"    -> Sessions after revoke: {len(sessions_after['sessions'])}")

    print("[*] Test F: Service denied after revoke")
    banner2 = connect_service("127.0.0.1", 2222)
    assert "DENIED" in banner2, f"Expected ACCESS DENIED after revoke, got: {banner2}"
    print(f"    -> Banner: {banner2.strip()}")

    print("[*] Test G: Wait for expiry daemon")
    api_post("/api/knock", {"host": "127.0.0.1", "sequence": [7000, 8000, 9000], "delay": 0.2})
    time.sleep(0.5)
    assert len(api_get("/api/sessions")["sessions"]) >= 1
    time.sleep(5.5)
    sessions_expired = api_get("/api/sessions")
    assert len(sessions_expired["sessions"]) == 0, "Expected sessions expired"
    print(f"    -> Sessions after expiry: {len(sessions_expired['sessions'])}")

    firewall.stop_expiry_daemon()
    print("\n[OK] Phase 6 full integration test passed!")


if __name__ == "__main__":
    main()

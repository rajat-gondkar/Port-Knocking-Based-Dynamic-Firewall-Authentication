"""
Tests for Phase 4: HTTP API endpoints
Run: python3 tests/test_phase4_api.py
"""
import sys
import json
import time
import threading
import urllib.request
import urllib.error
sys.path.insert(0, '/Users/rajat.gondkar/Desktop/NPS Project')

from server.logger import Logger
from server.firewall import FirewallManager
from server.sequence_tracker import SequenceTracker
from server.api_server import start_api_server


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
        "knock_ports": [7000, 8000, 9000, 7500],
        "sequence_timeout": 10,
        "access_duration": 30,
        "host": "0.0.0.0",
        "api_host": "127.0.0.1",
        "api_port": 8080,
        "log_file": "logs/api_test.log"
    }

    import os
    if os.path.exists(config["log_file"]):
        os.remove(config["log_file"])

    logger = Logger(config["log_file"])
    firewall = FirewallManager(config["service_port"], config["access_duration"], logger=logger)
    tracker = SequenceTracker(config["knock_sequence"], config["sequence_timeout"])

    # Seed some data
    firewall.open_port("10.0.0.1")
    firewall.open_port("10.0.0.2")
    logger.log("KNOCK_ATTEMPT", "192.168.1.1", 7000, "Progress: 1/3")
    logger.log("AUTH_SUCCESS", "192.168.1.1", 9000, "Sequence complete")

    api_thread = threading.Thread(
        target=start_api_server,
        args=(config, firewall, logger, tracker),
        daemon=True
    )
    api_thread.start()
    time.sleep(0.5)

    print("[*] Testing GET /api/status")
    status = api_get("/api/status")
    assert status["service_port"] == 2222
    assert status["sequence"] == [7000, 8000, 9000]
    print(f"    -> {status}")

    print("[*] Testing GET /api/sessions")
    sessions = api_get("/api/sessions")
    assert len(sessions["sessions"]) == 2
    print(f"    -> {len(sessions['sessions'])} sessions")

    print("[*] Testing GET /api/logs")
    logs = api_get("/api/logs?n=10")
    assert len(logs["logs"]) >= 2
    events = [e["event"] for e in logs["logs"]]
    assert "KNOCK_ATTEMPT" in events
    print(f"    -> {len(logs['logs'])} logs")

    print("[*] Testing POST /api/revoke")
    revoke = api_post("/api/revoke", {"ip": "10.0.0.1"})
    assert revoke["ok"] is True
    sessions = api_get("/api/sessions")
    assert len(sessions["sessions"]) == 1
    print(f"    -> Revoked 10.0.0.1, remaining sessions: {len(sessions['sessions'])}")

    print("[*] Testing POST /api/knock")
    knock = api_post("/api/knock", {"host": "127.0.0.1", "sequence": [7000], "delay": 0})
    assert knock["ok"] is True
    print(f"    -> {knock['message']}")

    print("[*] Testing GET / (frontend)")
    try:
        url = "http://127.0.0.1:8080/"
        with urllib.request.urlopen(url, timeout=3) as resp:
            html = resp.read().decode()
            assert "Port Knocking" in html or "<!DOCTYPE html>" in html or "<html>" in html
            print(f"    -> Served frontend/index.html ({len(html)} bytes)")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print("    -> frontend/index.html not found yet (expected before Phase 5)")
        else:
            raise

    print("\n[OK] All Phase 4 API tests passed!")


if __name__ == "__main__":
    main()

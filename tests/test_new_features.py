"""
Tests for new features: dynamic sequence config + port connection tester
Run: python3 tests/test_new_features.py
"""
import sys, json, time, threading, urllib.request, socket, os
sys.path.insert(0, '/Users/rajat.gondkar/Desktop/NPS Project')

from server.logger import Logger
from server.firewall import FirewallManager
from server.sequence_tracker import SequenceTracker
from server.knock_server import start_knock_listeners
from server.service import start_protected_service
from server.api_server import start_api_server


def api_post(path, data):
    url = f"http://127.0.0.1:8080{path}"
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode(),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return json.loads(e.read().decode())


def api_get(path):
    url = f"http://127.0.0.1:8080{path}"
    with urllib.request.urlopen(url, timeout=3) as resp:
        return json.loads(resp.read().decode())


def main():
    config = {
        "knock_sequence": [17000, 18000, 19000],
        "service_port": 12222,
        "knock_ports": [17000, 18000, 19000],
        "sequence_timeout": 10,
        "access_duration": 30,
        "host": "0.0.0.0",
        "api_host": "127.0.0.1",
        "api_port": 8080,
        "log_file": "logs/new_features.log"
    }

    if os.path.exists(config["log_file"]):
        os.remove(config["log_file"])

    logger = Logger(config["log_file"])
    firewall = FirewallManager(config["service_port"], config["access_duration"], logger=logger)
    tracker = SequenceTracker(config["knock_sequence"], config["sequence_timeout"])

    firewall.start_expiry_daemon()
    start_knock_listeners(config, tracker, firewall, logger)
    threading.Thread(target=start_protected_service, args=(config, firewall, logger), daemon=True).start()
    threading.Thread(target=start_api_server, args=(config, firewall, logger, tracker), daemon=True).start()

    time.sleep(1.0)
    print("[*] System ready. Sequence:", config["knock_sequence"])

    # Feature 1a: Update sequence with free ports
    print("\n[*] Feature 1a: Update sequence to [21000, 22000, 23000] (all free)")
    result = api_post("/api/config/sequence", {"sequence": [21000, 22000, 23000]})
    print(f"    -> {result}")
    assert result["ok"] is True, f"Expected ok=True, got {result}"

    time.sleep(0.5)
    status = api_get("/api/status")
    print(f"    -> New sequence from status: {status['sequence']}")
    assert status["sequence"] == [21000, 22000, 23000]

    # Feature 1b: Try to update sequence with an occupied port
    print("\n[*] Feature 1b: Try update sequence with occupied port 8080")
    result2 = api_post("/api/config/sequence", {"sequence": [8080, 22000, 23000]})
    print(f"    -> {result2}")
    assert result2["ok"] is False, "Expected failure because 8080 is in use by API server"
    assert 8080 in result2.get("occupied_ports", []), f"Expected 8080 in occupied_ports: {result2}"

    # Feature 2a: Test port connection - correct first knock via tester
    print("\n[*] Feature 2a: Test port 21000 (correct first knock)")
    result3 = api_post("/api/test-port", {"port": 21000, "host": "127.0.0.1"})
    print(f"    -> {result3}")
    assert result3["ok"] is True
    assert result3["connected"] is True

    time.sleep(0.3)
    logs = api_get("/api/logs?n=10")
    events = [e["event"] for e in logs["logs"]]
    print(f"    -> Events after test: {events}")
    assert "KNOCK_ATTEMPT" in events, f"Expected KNOCK_ATTEMPT in logs: {events}"

    # Feature 2b: Complete the sequence via tester
    print("\n[*] Feature 2b: Complete sequence via tester (22000, 23000)")
    api_post("/api/test-port", {"port": 22000, "host": "127.0.0.1"})
    time.sleep(0.2)
    api_post("/api/test-port", {"port": 23000, "host": "127.0.0.1"})
    time.sleep(0.3)

    logs2 = api_get("/api/logs?n=20")
    events2 = [e["event"] for e in logs2["logs"]]
    print(f"    -> Events after full sequence: {events2}")
    assert "AUTH_SUCCESS" in events2, f"Expected AUTH_SUCCESS in logs: {events2}"
    assert "PORT_OPENED" in events2, f"Expected PORT_OPENED in logs: {events2}"

    sessions = api_get("/api/sessions")
    assert len(sessions["sessions"]) >= 1, "Expected active session after completing sequence"
    print(f"    -> Active sessions: {len(sessions['sessions'])}")

    # Feature 2c: Test a wrong port (not in sequence)
    print("\n[*] Feature 2c: Test wrong port 9999 (not in sequence)")
    result4 = api_post("/api/test-port", {"port": 9999, "host": "127.0.0.1"})
    print(f"    -> {result4}")
    assert result4["ok"] is True
    assert result4["connected"] is False, "Expected connection failure for port 9999"

    # Feature 2d: Test a wrong port that IS monitored (breaks sequence)
    print("\n[*] Feature 2d: Test wrong monitored port 22000 after reset")
    # Reset by knocking wrong port
    api_post("/api/test-port", {"port": 21000, "host": "127.0.0.1"})
    time.sleep(0.2)
    api_post("/api/test-port", {"port": 22000, "host": "127.0.0.1"})
    time.sleep(0.2)
    api_post("/api/test-port", {"port": 21000, "host": "127.0.0.1"})  # wrong - should reset
    time.sleep(0.3)

    logs3 = api_get("/api/logs?n=30")
    auth_fails = [e for e in logs3["logs"] if e["event"] == "AUTH_FAIL"]
    print(f"    -> AUTH_FAIL events: {len(auth_fails)}")
    assert len(auth_fails) >= 1, "Expected at least one AUTH_FAIL after wrong knock"

    firewall.stop_expiry_daemon()
    print("\n[OK] All new feature tests passed!")


if __name__ == "__main__":
    main()

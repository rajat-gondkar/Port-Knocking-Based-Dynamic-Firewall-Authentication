"""
Final end-to-end verification using the actual config.json ports.
Run: python3 tests/test_final_e2e.py
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
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())


def api_get(path):
    url = f"http://127.0.0.1:8080{path}"
    with urllib.request.urlopen(url, timeout=3) as resp:
        return json.loads(resp.read().decode())


def knock(host, port):
    try:
        s = socket.socket()
        s.settimeout(2)
        s.connect((host, port))
        s.close()
    except:
        pass


def main():
    with open("config.json") as f:
        config = json.load(f)

    # Override API port to avoid conflicts
    config["api_host"] = "127.0.0.1"
    config["api_port"] = 8080
    config["log_file"] = "logs/final_e2e.log"

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
    print(f"[*] System started with sequence: {config['knock_sequence']}")

    # Step 1: Simulate knock via frontend API (exact frontend behavior)
    print("[*] Step 1: POST /api/knock (frontend simulation)")
    result = api_post("/api/knock", {"host": "127.0.0.1"})
    print(f"    -> {result}")
    time.sleep(0.5)

    # Step 2: Check logs
    print("[*] Step 2: Check logs via /api/logs")
    logs = api_get("/api/logs?n=50")
    for entry in logs["logs"]:
        print(f"    {entry['timestamp']} {entry['event']:15s} {entry['ip']}:{entry['port']} {entry['message']}")

    # Step 3: Check sessions
    print("[*] Step 3: Check active sessions")
    sessions = api_get("/api/sessions")
    print(f"    -> {len(sessions['sessions'])} active sessions: {[s['ip'] for s in sessions['sessions']]}")
    assert len(sessions["sessions"]) >= 1, "Expected at least 1 active session"

    # Step 4: Connect to service
    print(f"[*] Step 4: Connect to protected service on port {config['service_port']}")
    s = socket.socket()
    s.settimeout(3)
    s.connect(("127.0.0.1", config["service_port"]))
    banner = s.recv(1024).decode()
    s.close()
    print(f"    -> Banner: {banner.strip()}")
    assert "GRANTED" in banner

    # Step 5: Revoke and verify denied
    print("[*] Step 5: Revoke via API and verify denial")
    api_post("/api/revoke", {"ip": "127.0.0.1"})
    time.sleep(0.3)
    s2 = socket.socket()
    s2.settimeout(3)
    s2.connect(("127.0.0.1", config["service_port"]))
    banner2 = s2.recv(1024).decode()
    s2.close()
    print(f"    -> Banner: {banner2.strip()}")
    assert "DENIED" in banner2

    firewall.stop_expiry_daemon()
    print("\n[OK] Final end-to-end test passed with new ports!")


if __name__ == "__main__":
    main()

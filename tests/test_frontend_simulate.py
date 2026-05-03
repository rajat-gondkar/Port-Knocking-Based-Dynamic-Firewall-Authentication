"""
Reproduce exact frontend simulate knock flow to diagnose missing 7000 knock.
Run: python3 tests/test_frontend_simulate.py
"""
import sys, json, time, threading, urllib.request, socket
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


def main():
    config = {
        "knock_sequence": [7000, 8000, 9000],
        "service_port": 2222,
        "knock_ports": [7000, 8000, 9000, 7500, 8500],
        "sequence_timeout": 10,
        "access_duration": 30,
        "host": "0.0.0.0",
        "api_host": "127.0.0.1",
        "api_port": 8080,
        "log_file": "logs/frontend_simulate.log"
    }

    import os
    if os.path.exists(config["log_file"]):
        os.remove(config["log_file"])

    logger = Logger(config["log_file"])
    firewall = FirewallManager(config["service_port"], config["access_duration"], logger=logger)
    tracker = SequenceTracker(config["knock_sequence"], config["sequence_timeout"])

    firewall.start_expiry_daemon()
    start_knock_listeners(config, tracker, firewall, logger)

    threading.Thread(target=start_protected_service, args=(config, firewall, logger), daemon=True).start()
    threading.Thread(target=start_api_server, args=(config, firewall, logger, tracker), daemon=True).start()

    time.sleep(0.8)
    print("[*] System started. Calling /api/knock exactly like frontend does...")

    # Exact same payload as frontend
    result = api_post("/api/knock", {"host": "127.0.0.1"})
    print(f"    -> Response: {result}")

    time.sleep(0.3)

    print("[*] Fetching logs...")
    logs = api_get("/api/logs?n=50")
    for entry in logs["logs"]:
        print(f"    {entry['timestamp']} {entry['event']:15s} {entry['ip']}:{entry['port']} {entry['message']}")

    print("[*] Fetching sessions...")
    sessions = api_get("/api/sessions")
    print(f"    -> {len(sessions['sessions'])} active sessions")

    firewall.stop_expiry_daemon()


if __name__ == "__main__":
    main()

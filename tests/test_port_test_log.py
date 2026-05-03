"""
Quick verification that PORT_TEST events appear in the live log.
Run: python3 tests/test_port_test_log.py
"""
import sys, json, time, threading, urllib.request, os
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
        "knock_sequence": [17000, 18000, 19000],
        "service_port": 12222,
        "knock_ports": [17000, 18000, 19000],
        "sequence_timeout": 10,
        "access_duration": 30,
        "host": "0.0.0.0",
        "api_host": "127.0.0.1",
        "api_port": 8080,
        "log_file": "logs/port_test_log.log"
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

    print("[*] Testing a wrong port (not in sequence): 15551")
    result = api_post("/api/test-port", {"port": 15551, "host": "127.0.0.1"})
    print(f"    -> Popup: {result['message']}")

    time.sleep(0.3)

    logs = api_get("/api/logs?n=10")
    port_test_events = [e for e in logs["logs"] if e["event"] == "PORT_TEST"]
    print(f"    -> PORT_TEST events in log: {len(port_test_events)}")
    for e in port_test_events:
        print(f"       {e['timestamp']} {e['event']} {e['ip']}:{e['port']} {e['message']}")

    assert len(port_test_events) >= 1, "Expected at least one PORT_TEST event in logs"
    assert "15551" in port_test_events[0]["message"], "Expected port 15551 mentioned in log"
    assert "Failed" in port_test_events[0]["message"], "Expected failure message in log"

    print("\n[*] Testing a correct knock port: 17000")
    result2 = api_post("/api/test-port", {"port": 17000, "host": "127.0.0.1"})
    print(f"    -> Popup: {result2['message']}")

    time.sleep(0.3)

    logs2 = api_get("/api/logs?n=20")
    all_events = [e["event"] for e in logs2["logs"]]
    print(f"    -> Events: {all_events}")
    assert "PORT_TEST" in all_events, "Expected PORT_TEST in logs for correct port too"
    assert "KNOCK_ATTEMPT" in all_events, "Expected KNOCK_ATTEMPT from knock_server"

    firewall.stop_expiry_daemon()
    print("\n[OK] PORT_TEST logging works — wrong ports now show in the terminal!")


if __name__ == "__main__":
    main()

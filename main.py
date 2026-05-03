# main.py — start all components
import json
import threading
import os
import sys

from server.logger import Logger
from server.firewall import FirewallManager
from server.sequence_tracker import SequenceTracker
from server.knock_server import start_knock_listeners
from server.service import start_protected_service
from server.api_server import start_api_server


def main():
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
    try:
        with open(config_path) as f:
            config = json.load(f)
    except FileNotFoundError:
        print(f"[!] config.json not found at {config_path}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"[!] Invalid JSON in config.json: {e}")
        sys.exit(1)

    log_file = config.get("log_file", "logs/access.log")
    logger = Logger(log_file)
    firewall = FirewallManager(
        config.get("service_port", 2222),
        config.get("access_duration", 30),
        logger=logger
    )
    tracker = SequenceTracker(
        config.get("knock_sequence", []),
        config.get("sequence_timeout", 10)
    )

    firewall.start_expiry_daemon()

    # Start knock port listeners (threaded internally)
    try:
        start_knock_listeners(config, tracker, firewall, logger)
    except OSError as e:
        print(f"[!] Failed to start knock listeners: {e}")
        sys.exit(1)

    # Start protected service in a thread
    svc_thread = threading.Thread(
        target=start_protected_service,
        args=(config, firewall, logger),
        daemon=True
    )
    svc_thread.start()

    # Start HTTP API server in a thread
    api_thread = threading.Thread(
        target=start_api_server,
        args=(config, firewall, logger, tracker),
        daemon=True
    )
    api_thread.start()

    print(f"[*] Knock server running. Sequence: {config['knock_sequence']}")
    print(f"[*] Protected service on port {config['service_port']}")
    print(f"[*] Dashboard at http://localhost:8080/")

    # Keep main thread alive
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        print("\n[*] Shutting down...")
        firewall.stop_expiry_daemon()
        sys.exit(0)


if __name__ == "__main__":
    main()

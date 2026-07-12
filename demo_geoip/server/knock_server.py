import socket
import threading
import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from server.sequence_tracker import SequenceTracker
    from server.firewall import FirewallManager
    from server.logger import Logger

# Global state for managing active listener sockets and threads
_active_sockets: list[socket.socket] = []
_listener_threads: list[threading.Thread] = []


def _listen_on_port(port: int, host: str, tracker: "SequenceTracker", firewall: "FirewallManager", logger: "Logger"):
    """
    Bind a TCP socket to (host, port), accept connections,
    record the knock, and immediately close the connection.
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, port))
        sock.listen(5)
    except OSError as e:
        print(f"[!] Failed to bind to {host}:{port} — {e}")
        return

    # Register socket so it can be closed externally for restart
    _active_sockets.append(sock)

    print(f"[+] Knock listener started on {host}:{port}")

    while True:
        try:
            conn, addr = sock.accept()
            client_ip = addr[0]
            conn.close()

            success = tracker.record_knock(client_ip, port)
            progress = tracker.get_progress(client_ip)

            if success:
                from server.geoip import is_valid_location, get_location
                loc = get_location(client_ip)
                if is_valid_location(client_ip):
                    logger.log("AUTH_SUCCESS", client_ip, port, f"Sequence complete. Location: {loc}. Opening port.")
                    firewall.open_port(client_ip)
                else:
                    logger.log("GEOIP_BLOCKED", client_ip, port, f"Sequence complete, but location {loc} is blocked.")
            else:
                # If progress is 0 after this knock, it means wrong knock / reset
                if progress.startswith("0/"):
                    logger.log("AUTH_FAIL", client_ip, port, "Wrong knock or timeout — sequence reset")
                else:
                    logger.log("KNOCK_ATTEMPT", client_ip, port, f"Progress: {progress}")

        except OSError:
            # Socket likely closed
            break
        except Exception as e:
            print(f"[!] Error on knock port {port}: {e}")

    # Unregister on exit
    if sock in _active_sockets:
        _active_sockets.remove(sock)


def start_knock_listeners(config: dict, tracker: "SequenceTracker", firewall: "FirewallManager", logger: "Logger"):
    """
    For each port in config['knock_ports']:
      - Create a TCP socket bound to that port
      - Spawn a daemon thread: accept connection, extract client IP, close connection immediately
      - Call sequence_tracker.record_knock(ip, port)
      - If returns True: call firewall.open_port(ip) and log 'AUTH_SUCCESS'
      - Else: log 'KNOCK_ATTEMPT' with current progress
    """
    host = config.get("host", "0.0.0.0")
    knock_ports = config.get("knock_ports", [])

    for port in knock_ports:
        t = threading.Thread(
            target=_listen_on_port,
            args=(port, host, tracker, firewall, logger),
            daemon=True,
            name=f"KnockListener-{port}"
        )
        t.start()
        _listener_threads.append(t)


def stop_knock_listeners():
    """Close all active listener sockets to break accept() loops and stop threads."""
    for sock in list(_active_sockets):
        try:
            sock.close()
        except Exception:
            pass
    _active_sockets.clear()
    _listener_threads.clear()


def restart_knock_listeners(config: dict, tracker: "SequenceTracker", firewall: "FirewallManager", logger: "Logger"):
    """Stop existing knock listeners and start new ones with updated config."""
    print("[*] Restarting knock listeners with new ports...")
    stop_knock_listeners()
    # Give threads a moment to exit their loops
    threading.Event().wait(0.3)
    start_knock_listeners(config, tracker, firewall, logger)
    print(f"[+] Knock listeners restarted on {config.get('knock_ports', [])}")


def is_port_free(host: str, port: int) -> bool:
    """Check if a TCP port is free by attempting to bind a temporary socket.
    Does NOT use SO_REUSEADDR so any existing listener blocks this bind."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Do NOT set SO_REUSEADDR — we want strict conflict detection
        s.bind((host, port))
        s.close()
        return True
    except OSError:
        return False

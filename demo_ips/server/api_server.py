import json
import os
import socket
import threading
import time
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from server.firewall import FirewallManager
    from server.logger import Logger
    from server.sequence_tracker import SequenceTracker


# Simple knock helper used by POST /api/knock demo endpoint
def _demo_knock(host: str, port: int):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2)
        s.connect((host, port))
        time.sleep(0.05)  # Brief pause so server can process before client closes
        s.close()
    except Exception:
        pass


def make_handler(config: dict, firewall: "FirewallManager", logger: "Logger", tracker: "SequenceTracker"):
    """
    Factory that returns a BaseHTTPRequestHandler subclass with access
    to config, firewall, logger, and tracker.
    """

    class APIHandler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            # Suppress default console logging
            pass

        def _send_json(self, data: dict, status: int = 200):
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()
            self.wfile.write(json.dumps(data).encode())

        def do_OPTIONS(self):
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()

        def do_GET(self):
            path = self.path

            if path == "/":
                self._serve_frontend()
                return

            if path == "/api/status":
                self._send_json({
                    "knock_ports": config.get("knock_ports", []),
                    "service_port": config.get("service_port", 2222),
                    "sequence": config.get("knock_sequence", [])
                })
                return

            if path == "/api/sessions":
                sessions = firewall.get_active_sessions()
                self._send_json({"sessions": sessions})
                return

            if path == "/api/bans":
                bans = tracker.get_bans()
                self._send_json({"bans": bans})
                return

            if path == "/api/strikes":
                with tracker.lock:
                    strikes_data = [
                        {"ip": ip, "strikes": count, "max": tracker.max_strikes}
                        for ip, count in tracker.strikes.items()
                        if ip not in tracker.banned_ips
                    ]
                self._send_json({"strikes": strikes_data})
                return

            if path.startswith("/api/logs"):
                n = 50
                if "?" in path:
                    query = path.split("?", 1)[1]
                    for param in query.split("&"):
                        if param.startswith("n="):
                            try:
                                n = int(param.split("=", 1)[1])
                            except ValueError:
                                pass
                logs = logger.get_recent(n)
                self._send_json({"logs": logs})
                return

            self._send_json({"error": "Not found"}, 404)

        def do_POST(self):
            path = self.path
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode() if content_length > 0 else "{}"

            try:
                payload = json.loads(body) if body else {}
            except json.JSONDecodeError:
                self._send_json({"error": "Invalid JSON"}, 400)
                return

            if path == "/api/revoke":
                ip = payload.get("ip")
                if not ip:
                    self._send_json({"error": "Missing 'ip' field"}, 400)
                    return
                firewall.close_port(ip)
                logger.log("PORT_CLOSED", ip, config.get("service_port"), "Revoked via API")
                self._send_json({"ok": True})
                return

            if path == "/api/unban":
                ip = payload.get("ip")
                if not ip:
                    self._send_json({"error": "Missing 'ip' field"}, 400)
                    return
                with tracker.lock:
                    tracker.banned_ips.pop(ip, None)
                    tracker.strikes.pop(ip, None)
                    tracker.sessions.pop(ip, None)
                logger.log("BAN_LIFTED", ip, None, "Manually unbanned via dashboard")
                self._send_json({"ok": True})
                return

            if path == "/api/knock":
                host = payload.get("host", "127.0.0.1")
                sequence = payload.get("sequence", config.get("knock_sequence", []))
                delay = payload.get("delay", 0.5)
                for port in sequence:
                    _demo_knock(host, port)
                    if delay:
                        time.sleep(delay)
                self._send_json({"ok": True, "message": f"Knocked {host} with {sequence}"})
                return

            if path == "/api/config/sequence":
                new_sequence = payload.get("sequence", [])
                if not isinstance(new_sequence, list) or len(new_sequence) == 0:
                    self._send_json({"ok": False, "error": "sequence must be a non-empty list of integers"}, 400)
                    return

                # Validate all entries are ints > 1024
                bad = [p for p in new_sequence if not isinstance(p, int) or p <= 1024]
                if bad:
                    self._send_json({"ok": False, "error": f"All ports must be integers > 1024. Invalid: {bad}"}, 400)
                    return

                # Check if ports are free (skip ports we already own)
                host = config.get("host", "0.0.0.0")
                # Import here to avoid circular import issues at module level
                from server.knock_server import is_port_free, restart_knock_listeners

                current_ports = set(config.get("knock_ports", []))
                occupied = [p for p in new_sequence if p not in current_ports and not is_port_free(host, p)]
                if occupied:
                    self._send_json({
                        "ok": False,
                        "error": f"Port(s) already in use: {occupied}. Please change them.",
                        "occupied_ports": occupied
                    }, 409)
                    return

                # Update config and tracker
                config["knock_sequence"] = new_sequence
                
                # Preserve existing knock ports as honeypots/decoys
                decoys = [p for p in current_ports if p not in new_sequence]
                if not decoys:
                    decoys = [17500, 18500, 19500]
                config["knock_ports"] = new_sequence + decoys
                
                tracker.expected_sequence = new_sequence

                # Restart listeners
                restart_knock_listeners(config, tracker, firewall, logger)

                logger.log("CONFIG_UPDATE", "127.0.0.1", None, f"Sequence changed to {new_sequence}")
                self._send_json({"ok": True, "sequence": new_sequence})
                return

            if path == "/api/test-port":
                port = payload.get("port")
                if not isinstance(port, int) or port <= 0:
                    self._send_json({"ok": False, "error": "port must be a positive integer"}, 400)
                    return

                target_host = payload.get("host", "127.0.0.1")
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.settimeout(2)
                    s.connect((target_host, port))
                    time.sleep(0.05)
                    s.close()
                    connected = True
                    msg = f"Successfully connected to {target_host}:{port}"
                except Exception as e:
                    connected = False
                    msg = f"Failed to connect to {target_host}:{port} — {e}"

                # Only log failed tests — successful knock ports are already logged by knock_server.py
                if not connected:
                    logger.log("PORT_TEST", target_host, port, msg)

                self._send_json({"ok": True, "connected": connected, "message": msg, "port": port})
                return

            self._send_json({"error": "Not found"}, 404)

        def _serve_frontend(self):
            # Serve frontend/index.html
            script_dir = os.path.dirname(os.path.abspath(__file__))
            frontend_path = os.path.join(script_dir, "..", "frontend", "index.html")
            if not os.path.exists(frontend_path):
                frontend_path = os.path.join(os.getcwd(), "frontend", "index.html")

            if os.path.exists(frontend_path):
                with open(frontend_path, "r") as f:
                    html = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(html.encode())
            else:
                self._send_json({"error": "frontend/index.html not found"}, 404)

    return APIHandler


def start_api_server(config: dict, firewall: "FirewallManager", logger: "Logger", tracker: "SequenceTracker"):
    """
    Start the HTTP API server in the current thread.
    (Caller should spawn this in a daemon thread if desired.)
    """
    host = config.get("api_host", "0.0.0.0")
    port = config.get("api_port", 8080)

    handler = make_handler(config, firewall, logger, tracker)
    server = ThreadingHTTPServer((host, port), handler)

    print(f"[+] API server started on http://{host}:{port}/")
    try:
        server.serve_forever()
    except OSError as e:
        print(f"[!] API server failed to start on {host}:{port} — {e}")

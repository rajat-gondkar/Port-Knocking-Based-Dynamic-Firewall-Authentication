# Port Knocking-Based Dynamic Firewall Authentication
## Implementation Guide for Coding Agent

---

## Project Overview

Implement a **Port Knocking** security system where:
- A server silently monitors multiple ports
- A client sends TCP connection attempts to a predefined sequence of ports (the "knock")
- If the sequence matches, the server dynamically opens a protected service port **only for that client IP**
- Access is revoked after a timeout or explicit close
- All attempts are logged

**Stack:** Python (sockets, threading), with a lightweight HTML/CSS/JS frontend dashboard.

---

## Architecture

```
Client                      Server
  |                           |
  |-- knock port 7000 ------> |  (attempt 1)
  |-- knock port 8000 ------> |  (attempt 2)
  |-- knock port 9000 ------> |  (attempt 3 - sequence complete)
  |                           |  -> opens port 2222 for this IP
  |-- connect port 2222 ----> |  (protected service access granted)
  |                           |
```

**Components:**
- `server/knock_server.py` — monitors knock ports, validates sequences, manages firewall state
- `server/firewall.py` — manages per-IP access rules (in-memory simulation, optionally real iptables)
- `server/logger.py` — structured logging of all events
- `client/knock_client.py` — sends knock sequence, then connects to service
- `frontend/index.html` — single-file dashboard (real-time logs, active sessions, sequence config)
- `config.json` — knock sequence, ports, timeout settings

---

## Phase 1 — Core Server: Port Monitor & Sequence Tracker

**Goal:** Server listens on multiple knock ports and tracks per-IP knock attempts.

### Files to create:
- `config.json`
- `server/knock_server.py`
- `server/sequence_tracker.py`

### `config.json`
```json
{
  "knock_sequence": [7000, 8000, 9000],
  "service_port": 2222,
  "knock_ports": [7000, 8000, 9000, 7500, 8500],
  "sequence_timeout": 10,
  "access_duration": 30,
  "host": "0.0.0.0",
  "log_file": "logs/access.log"
}
```

### `server/sequence_tracker.py`

Implement a `SequenceTracker` class:

```python
# Manages per-IP knock state
class SequenceTracker:
    def __init__(self, expected_sequence: list[int], timeout: int):
        # self.sessions: dict[ip_str, {"progress": int, "last_time": float}]
        pass

    def record_knock(self, ip: str, port: int) -> bool:
        """
        Record a knock attempt from `ip` on `port`.
        - If port matches the next expected port in sequence, advance progress.
        - If progress completes the full sequence, return True (authenticated).
        - If timeout exceeded since last knock, reset progress for that IP.
        - If wrong port knocked, reset progress for that IP.
        - Returns False in all non-completion cases.
        """
        pass

    def reset(self, ip: str):
        """Clear knock state for an IP."""
        pass
```

### `server/knock_server.py`

Implement a multi-threaded server:

```python
# Pseudocode — implement fully
def start_knock_listeners(config):
    """
    For each port in config["knock_ports"]:
      - Create a TCP socket bound to that port
      - Spawn a thread: accept connection, extract client IP, close connection immediately
      - Call sequence_tracker.record_knock(ip, port)
      - If returns True: call firewall.open_port(ip) and log "AUTH_SUCCESS"
      - Else: log "KNOCK_ATTEMPT" with current progress
    """
    pass
```

**Requirements:**
- Each port listener runs in its own daemon thread
- Connections are accepted and immediately closed (no data exchange on knock ports)
- Sequence tracker is shared across all listener threads (use threading.Lock inside tracker)
- Load config from `config.json`

---

## Phase 2 — Firewall Manager & Protected Service

**Goal:** Dynamically open/close access to the service port per-IP, and run a minimal protected service.

### Files to create:
- `server/firewall.py`
- `server/service.py`

### `server/firewall.py`

```python
# In-memory firewall (no root required). Optionally extend to real iptables.
class FirewallManager:
    def __init__(self, service_port: int, access_duration: int):
        # self.allowed_ips: dict[ip, expiry_timestamp]
        pass

    def open_port(self, ip: str):
        """Add IP to allowed set with expiry = now + access_duration. Log the action."""
        pass

    def close_port(self, ip: str):
        """Remove IP from allowed set. Log the action."""
        pass

    def is_allowed(self, ip: str) -> bool:
        """Return True if IP is in allowed set and not expired. Auto-expire if past time."""
        pass

    def get_active_sessions(self) -> list[dict]:
        """Return list of {ip, expires_at, remaining_seconds} for all active IPs."""
        pass

    def start_expiry_daemon(self):
        """Background thread: every 5 seconds, call is_allowed() for all IPs to prune expired ones."""
        pass
```

### `server/service.py`

```python
# A minimal TCP service that respects firewall rules
def start_protected_service(config, firewall: FirewallManager):
    """
    - Bind a TCP socket to config["service_port"]
    - On each connection: check firewall.is_allowed(client_ip)
      - If allowed: send welcome banner "ACCESS GRANTED. Welcome, {ip}." then echo input back
      - If not allowed: send "ACCESS DENIED." and close immediately
    - Log all connection attempts
    """
    pass
```

---

## Phase 3 — Logger & Client

**Goal:** Structured logging and a functional knock client.

### Files to create:
- `server/logger.py`
- `client/knock_client.py`

### `server/logger.py`

```python
import json, time

class Logger:
    def __init__(self, log_file: str):
        pass

    def log(self, event_type: str, ip: str, port: int = None, message: str = ""):
        """
        Write a JSON line to log_file and also keep last 100 events in memory.
        Format: {"timestamp": ISO8601, "event": event_type, "ip": ip, "port": port, "message": message}
        
        Event types used in the project:
          KNOCK_ATTEMPT   - a knock was received (include current progress e.g. "2/3")
          AUTH_SUCCESS    - full sequence matched, port opened
          AUTH_FAIL       - wrong knock, sequence reset
          ACCESS_GRANTED  - service connection allowed
          ACCESS_DENIED   - service connection rejected
          PORT_OPENED     - firewall opened for IP
          PORT_CLOSED     - firewall closed for IP (timeout or manual)
        """
        pass

    def get_recent(self, n: int = 50) -> list[dict]:
        """Return last n in-memory log entries."""
        pass
```

### `client/knock_client.py`

```python
import socket, time, json, sys

def knock(host: str, port: int):
    """Open a TCP connection to host:port and immediately close it."""
    try:
        s = socket.socket()
        s.settimeout(2)
        s.connect((host, port))
        s.close()
    except:
        pass  # Expected — server closes immediately

def run_knock_sequence(host: str, sequence: list[int], delay: float = 0.5):
    """Send knock to each port in sequence with `delay` seconds between each."""
    print(f"[*] Starting knock sequence on {host}: {sequence}")
    for port in sequence:
        knock(host, port)
        print(f"  [+] Knocked port {port}")
        time.sleep(delay)
    print("[*] Sequence complete. Attempting service connection...")

def connect_to_service(host: str, service_port: int):
    """Connect to service port and print server response."""
    try:
        s = socket.socket()
        s.settimeout(5)
        s.connect((host, service_port))
        banner = s.recv(1024).decode()
        print(f"[SERVICE] {banner}")
        s.close()
    except Exception as e:
        print(f"[!] Service connection failed: {e}")

if __name__ == "__main__":
    with open("config.json") as f:
        config = json.load(f)
    host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    run_knock_sequence(host, config["knock_sequence"])
    time.sleep(0.5)
    connect_to_service(host, config["service_port"])
```

---

## Phase 4 — HTTP API for Frontend

**Goal:** A lightweight HTTP server that exposes endpoints the dashboard will poll.

### File to create:
- `server/api_server.py`

Use only Python stdlib (`http.server`, `json`). No Flask required.

### Endpoints to implement:

| Method | Path | Response |
|--------|------|----------|
| GET | `/api/status` | `{"knock_ports": [...], "service_port": int, "sequence": [...]}` |
| GET | `/api/sessions` | `{"sessions": [{ip, expires_at, remaining_seconds}, ...]}` |
| GET | `/api/logs?n=50` | `{"logs": [{timestamp, event, ip, port, message}, ...]}` |
| POST | `/api/revoke` | Body: `{"ip": "x.x.x.x"}` → revoke access, return `{"ok": true}` |
| POST | `/api/knock` | Body: `{"host": "...", "sequence": [...]}` → trigger client knock (for demo) |

### Implementation notes:
- Inherit from `BaseHTTPRequestHandler`
- Start API server in a daemon thread on port `8080`
- Add `Access-Control-Allow-Origin: *` header to all responses (CORS)
- Share the same `Logger` and `FirewallManager` instances used by the knock server

---

## Phase 5 — Frontend Dashboard

**Goal:** A single `frontend/index.html` file — no build tools, no frameworks. Plain HTML + CSS + JS.

### Design Requirements:
- Dark terminal-inspired theme (dark background, green/cyan accents, monospace font)
- Three panels in a simple layout:
  1. **Status Panel** — shows knock sequence, service port, knock ports
  2. **Active Sessions Panel** — table of allowed IPs with time remaining (auto-refresh countdown)
  3. **Live Log Panel** — scrollable list of recent log entries, color-coded by event type

### Color coding for log events:
- `AUTH_SUCCESS` → green
- `ACCESS_DENIED` / `AUTH_FAIL` → red  
- `KNOCK_ATTEMPT` → yellow
- `PORT_OPENED` / `PORT_CLOSED` → cyan
- All others → white/grey

### Interactivity:
- **Revoke button** next to each active session row — calls `POST /api/revoke`
- **Simulate Knock button** — form with host input, calls `POST /api/knock` (demo purposes)
- Auto-refresh every 3 seconds via `setInterval` polling `/api/logs` and `/api/sessions`

### Layout (simple CSS grid, no framework):

```
┌──────────────────────────────────────────────────┐
│  🔒  Port Knocking Dashboard                      │
├────────────────┬─────────────────────────────────┤
│ STATUS         │ ACTIVE SESSIONS                  │
│ Sequence: ...  │ IP | Expires | Remaining | Revoke│
│ Service: 2222  │ ...                              │
│ Monitoring: .. │                                  │
├────────────────┴─────────────────────────────────┤
│ LIVE ACCESS LOG                                   │
│ [timestamp] [EVENT]  ip:port  message             │
│ ...                                               │
└──────────────────────────────────────────────────┘
```

### Fetch pattern to use:

```javascript
async function refresh() {
  const [logsRes, sessionsRes] = await Promise.all([
    fetch('/api/logs?n=50'),
    fetch('/api/sessions')
  ]);
  const { logs } = await logsRes.json();
  const { sessions } = await sessionsRes.json();
  renderLogs(logs);
  renderSessions(sessions);
}
setInterval(refresh, 3000);
refresh();
```

---

## Phase 6 — Integration & Entry Point

**Goal:** Wire all components together into a single runnable entry point.

### File to create:
- `main.py`

```python
# main.py — start all components
import json, threading
from server.logger import Logger
from server.firewall import FirewallManager
from server.sequence_tracker import SequenceTracker
from server.knock_server import start_knock_listeners
from server.service import start_protected_service
from server.api_server import start_api_server

def main():
    with open("config.json") as f:
        config = json.load(f)

    logger = Logger(config["log_file"])
    firewall = FirewallManager(config["service_port"], config["access_duration"])
    tracker = SequenceTracker(config["knock_sequence"], config["sequence_timeout"])

    firewall.start_expiry_daemon()

    # Start knock port listeners (threaded internally)
    start_knock_listeners(config, tracker, firewall, logger)

    # Start protected service in a thread
    threading.Thread(
        target=start_protected_service,
        args=(config, firewall, logger),
        daemon=True
    ).start()

    # Start HTTP API server in a thread
    threading.Thread(
        target=start_api_server,
        args=(config, firewall, logger),
        daemon=True
    ).start()

    print(f"[*] Knock server running. Sequence: {config['knock_sequence']}")
    print(f"[*] Protected service on port {config['service_port']}")
    print(f"[*] Dashboard at http://localhost:8080/")
    
    # Keep main thread alive
    threading.Event().wait()

if __name__ == "__main__":
    main()
```

---

## Final Project Structure

```
port-knocking/
├── config.json
├── main.py
├── server/
│   ├── __init__.py
│   ├── knock_server.py
│   ├── sequence_tracker.py
│   ├── firewall.py
│   ├── service.py
│   ├── logger.py
│   └── api_server.py
├── client/
│   ├── __init__.py
│   └── knock_client.py
├── frontend/
│   └── index.html
└── logs/
    └── access.log
```

---

## Constraints & Notes for Agent

- **No external dependencies** — use only Python stdlib (`socket`, `threading`, `http.server`, `json`, `time`, `logging`)
- **No root/sudo required** — firewall is in-memory only; skip actual `iptables` commands unless the environment supports it
- **Thread safety** — all shared state (`SequenceTracker`, `FirewallManager`, `Logger`) must use `threading.Lock()`
- **Ports** — use ports above 1024 to avoid needing root. Default: knocks on 7000/8000/9000, service on 2222, API on 8080
- **Frontend is a single file** — `frontend/index.html` must be self-contained with inline `<style>` and `<script>`. The API server should serve it at `GET /`
- **Graceful handling** — catch `OSError` for port-already-in-use; log and exit with a clear message
- Implement phases in order — each phase produces independently testable output before moving to the next

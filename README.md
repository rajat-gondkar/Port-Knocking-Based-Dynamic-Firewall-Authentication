# Port Knocking-Based Dynamic Firewall Authentication

A complete, self-contained port knocking security system built with Python (stdlib only) and a single-file HTML/CSS/JS frontend dashboard. No external dependencies. No root required.

---

## What is Port Knocking?

Port knocking is a stealth authentication technique where a client "knocks" on a predefined sequence of closed ports. If the sequence matches, the server dynamically opens a protected service port **only for that client's IP**. If the sequence is wrong or incomplete, the server remains silent and access is denied.

```
Client                      Server
  |                           |
  |-- knock port 17000 ----> |  (attempt 1)
  |-- knock port 18000 ----> |  (attempt 2)
  |-- knock port 19000 ----> |  (attempt 3 - sequence complete)
  |                           |  -> opens port 12222 for this IP
  |-- connect port 12222 ---> |  (protected service access granted)
  |                           |
```

---

## Features

- **Multi-threaded knock listeners** — silently monitors multiple ports concurrently
- **Per-IP sequence tracking** — each client has independent knock state with timeout protection
- **Dynamic firewall (in-memory)** — opens/closes access per-IP with configurable TTL
- **Structured JSON logging** — all events logged to disk + in-memory ring buffer for real-time display
- **Web dashboard** — dark terminal-themed UI with live logs, active sessions, and controls
- **Custom knock sequences** — change the knock port sequence on the fly via the dashboard
- **Port connection tester** — manually test any port and see knock/auth results in the live terminal
- **Zero dependencies** — uses only Python standard library (`socket`, `threading`, `http.server`, `json`)
- **No root/sudo required** — all ports above 1024, firewall is simulated in-memory

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3 (stdlib only) |
| Frontend | Vanilla HTML5 + CSS3 + JS (single file, no build tools) |
| Protocols | TCP (knock + service), HTTP (API + dashboard) |
| Concurrency | `threading` (daemon threads for listeners, service, API, expiry) |

---

## Quick Start

### 1. Clone / Download

```bash
git clone <repo-url>
cd port-knocking
```

### 2. Run the Server

```bash
python3 main.py
```

You should see:

```
[+] Knock listener started on 0.0.0.0:17000
[+] Knock listener started on 0.0.0.0:18000
[+] Knock listener started on 0.0.0.0:19000
[+] Knock listener started on 0.0.0.0:17500
[+] Knock listener started on 0.0.0.0:18500
[+] Protected service started on 0.0.0.0:12222
[+] API server started on http://127.0.0.1:8080/
[*] Knock server running. Sequence: [17000, 18000, 19000]
[*] Protected service on port 12222
[*] Dashboard at http://localhost:8080/
```

### 3. Open the Dashboard

Navigate to **http://localhost:8080/**

### 4. Send a Knock Sequence

**Option A — Dashboard:**
- Click **Send Knock Sequence** in the Status Panel
- Or enter your own ports in **Custom Sequence** and click **Update Sequence**

**Option B — CLI Client:**
```bash
python3 client/knock_client.py
```

**Option C — Manual (netcat/telnet):**
```bash
nc -z 127.0.0.1 17000 && nc -z 127.0.0.1 18000 && nc -z 127.0.0.1 19000
```

### 5. Connect to the Protected Service

Once authenticated, connect to the service port:
```bash
telnet 127.0.0.1 12222
```

You should see:
```
ACCESS GRANTED. Welcome, 127.0.0.1.
```

---

## Dashboard Guide

The dashboard is a single self-contained page served at `http://localhost:8080/`.

### Layout

```
+----------------------------------------------------------+
|  🔒  Port Knocking Dashboard                              |
+----------------------------+-----------------------------+
| STATUS                     | ACTIVE SESSIONS             |
| Sequence: 17000→18000→19000| IP | Expires | Remaining    |
| Service: 12222             | ...                         |
| Monitoring: 17000 18000 ...|                             |
|                            |                             |
| Custom Sequence            |                             |
| [__________] [Update]      |                             |
|                            |                             |
| Test Port Connection       |                             |
| [__________] [Test]        |                             |
|                            |                             |
| Simulate Knock             |                             |
| [127.0.0.1] [Send]        |                             |
+----------------------------+-----------------------------+
| LIVE ACCESS LOG                                           |
| [timestamp] [EVENT] ip:port message                       |
| ...                                                       |
+----------------------------------------------------------+
```

### Panels

| Panel | Description |
|-------|-------------|
| **Status** | Current knock sequence, service port, monitored ports |
| **Custom Sequence** | Enter comma-separated ports (e.g. `20000,30000,40000`) and update. Occupied ports are rejected with a toast error. |
| **Test Port Connection** | Enter any port and test connectivity. If it's a knock port, the result appears in the Live Log as a real knock attempt. |
| **Simulate Knock** | Automatically sends the full configured sequence to a target host. |
| **Active Sessions** | Table of authenticated IPs with expiry countdown and **Revoke** button. |
| **Live Access Log** | Real-time scrollable log, color-coded by event type. Auto-refreshes every 3 seconds. |

### Log Color Coding

| Event | Color |
|-------|-------|
| `AUTH_SUCCESS` / `ACCESS_GRANTED` | Green |
| `ACCESS_DENIED` / `AUTH_FAIL` | Red |
| `KNOCK_ATTEMPT` | Yellow |
| `PORT_OPENED` / `PORT_CLOSED` | Cyan |
| Others | White/Grey |

---

## Configuration

All settings are in `config.json`:

```json
{
  "knock_sequence": [17000, 18000, 19000],
  "service_port": 12222,
  "knock_ports": [17000, 18000, 19000, 17500, 18500],
  "sequence_timeout": 10,
  "access_duration": 30,
  "host": "0.0.0.0",
  "log_file": "logs/access.log"
}
```

| Key | Description |
|-----|-------------|
| `knock_sequence` | The ordered ports a client must knock to authenticate |
| `service_port` | The protected TCP service port opened after successful knock |
| `knock_ports` | All ports the server listens on (sequence + decoy/extra monitors) |
| `sequence_timeout` | Seconds allowed between consecutive knocks before reset |
| `access_duration` | Seconds an IP remains allowed after successful authentication |
| `host` | Bind address for listeners and service (`0.0.0.0` = all interfaces) |
| `log_file` | Path to structured JSON log file |

> **Port Selection Tip:** On macOS, port `7000` is used by ControlCe. The defaults use `17000+` to avoid system conflicts. You can change these freely as long as they are `> 1024` and not in use.

---

## API Reference

The HTTP API runs on port `8080` with CORS enabled.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Serves the dashboard (`frontend/index.html`) |
| `GET` | `/api/status` | Returns current knock sequence, service port, monitored ports |
| `GET` | `/api/sessions` | Returns list of active authenticated sessions |
| `GET` | `/api/logs?n=50` | Returns last `n` in-memory log entries |
| `POST` | `/api/knock` | Body: `{"host":"...","sequence":[...],"delay":0.5}` — simulate a knock |
| `POST` | `/api/revoke` | Body: `{"ip":"..."}` — manually revoke access for an IP |
| `POST` | `/api/config/sequence` | Body: `{"sequence":[...]}` — change knock sequence dynamically |
| `POST` | `/api/test-port` | Body: `{"port":1234,"host":"127.0.0.1"}` — test TCP connectivity |

---

## Project Structure

```
port-knocking/
├── config.json                 # Central configuration
├── main.py                     # Entry point — boots all components
├── README.md                   # This file
├── project_report.md           # Detailed implementation report
├── server/
│   ├── __init__.py
│   ├── knock_server.py         # Multi-threaded knock port listeners (with restart support)
│   ├── sequence_tracker.py     # Per-IP knock state machine
│   ├── firewall.py             # In-memory firewall with TTL
│   ├── service.py              # Protected TCP echo service
│   ├── logger.py               # Structured JSON + in-memory logging
│   └── api_server.py           # HTTP API for dashboard
├── client/
│   ├── __init__.py
│   └── knock_client.py         # CLI knock client
├── frontend/
│   └── index.html              # Self-contained real-time dashboard
├── tests/
│   ├── test_sequence_tracker.py
│   ├── test_knock_server.py
│   ├── test_phase2.py
│   ├── test_phase3_e2e.py
│   ├── test_phase4_api.py
│   ├── test_phase6_integration.py
│   ├── test_final_e2e.py
│   └── test_new_features.py
└── logs/
    └── access.log              # Runtime structured logs
```

---

## Architecture

### Components

| Component | Responsibility |
|-----------|--------------|
| **SequenceTracker** | Thread-safe per-IP knock progress tracking with timeout and reset logic |
| **KnockServer** | Spawns a TCP listener thread per knock port. Closes connections immediately and records knocks. Supports dynamic restart for sequence changes. |
| **FirewallManager** | In-memory allow-list with TTL. Auto-expires entries. Background daemon prunes stale sessions every 5s. |
| **ProtectedService** | Minimal TCP echo service gated by the firewall. Sends banner + echoes input for allowed IPs. |
| **Logger** | Structured JSON line output to disk + in-memory ring buffer (last 100 events) for dashboard polling. |
| **APIServer** | `http.server` providing REST endpoints and serving the single-file frontend. |

### Authentication Flow

1. Client connects to first knock port → server logs `KNOCK_ATTEMPT` (progress 1/3)
2. Client connects to second knock port within timeout → `KNOCK_ATTEMPT` (progress 2/3)
3. Client connects to third knock port within timeout → `AUTH_SUCCESS`, firewall opens service port for client's IP, logs `PORT_OPENED`
4. Client connects to service port → `ACCESS_GRANTED`, receives welcome banner
5. After `access_duration` seconds → firewall auto-expires IP, logs `PORT_CLOSED`

### Security Notes

- **No encryption** — this is a demonstration/prototype system. In production, the protected service should use TLS.
- **In-memory firewall** — does not modify real `iptables`. Extend `firewall.py` to call `iptables` if needed.
- **Sequence secrecy** — the knock sequence acts like a shared secret. Keep `config.json` secure.
- **Timeout protection** — partial sequences expire after `sequence_timeout` seconds to prevent brute-force guessing.

---

## Testing

All tests use only Python stdlib (`unittest` not required; plain assertions used).

```bash
# Unit tests
python3 tests/test_sequence_tracker.py
python3 tests/test_phase2.py

# Smoke / integration tests
python3 tests/test_knock_server.py
python3 tests/test_phase3_e2e.py
python3 tests/test_phase4_api.py
python3 tests/test_phase6_integration.py
python3 tests/test_final_e2e.py

# New feature tests (dynamic sequence + port tester)
python3 tests/test_new_features.py
```

Run all tests at once:
```bash
for f in tests/test_*.py; do echo "=== $f ==="; python3 "$f"; done
```

---

## Troubleshooting

### "Failed to bind to X — Address already in use"

A port in your `config.json` is occupied by another process.

**Check what's using it:**
```bash
lsof -i :<port>
```

**Fix:** Change the port in `config.json` or use the dashboard's **Custom Sequence** form to pick free ports.

> **macOS users:** Port `7000` is used by ControlCe. The default config avoids this by using `17000+`.

### Dashboard shows no events after Simulate Knock

1. Check that all knock listeners started successfully in the terminal output.
2. Verify the sequence in the dashboard Status panel matches the monitored ports.
3. Try the **Test Port Connection** form to manually test each port.

### "Connection refused" when connecting to service

You haven't completed the knock sequence, or the session has expired. Check the **Live Access Log** for `ACCESS_DENIED` or `AUTH_FAIL` events.

---

## License

MIT — free to use, modify, and distribute.

---

## Acknowledgments

Built as an educational implementation of the port knocking security concept using Python's standard library only.

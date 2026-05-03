# Project Report: Port Knocking-Based Dynamic Firewall Authentication

**Project:** Port Knocking-Based Dynamic Firewall Authentication
**Stack:** Python (stdlib only: `socket`, `threading`, `http.server`, `json`, `time`), HTML/CSS/JS (single file, no build tools)
**Date Started:** 2026-05-03
**Status:** Phase 0 — Planning Complete

---

## Table of Contents

1. [Phase 0 — Planning & Architecture](#phase-0--planning--architecture)
2. [Phase 1 — Core Server: Port Monitor & Sequence Tracker](#phase-1--core-server-port-monitor--sequence-tracker)
3. [Phase 2 — Firewall Manager & Protected Service](#phase-2--firewall-manager--protected-service)
4. [Phase 3 — Logger & Client](#phase-3--logger--client)
5. [Phase 4 — HTTP API for Frontend](#phase-4--http-api-for-frontend)
6. [Phase 5 — Frontend Dashboard](#phase-5--frontend-dashboard)
7. [Phase 6 — Integration & Entry Point](#phase-6--integration--entry-point)
8. [Appendix: Final Project Structure](#appendix-final-project-structure)
9. [Appendix: Configuration](#appendix-configuration)

---

## Phase 0 — Planning & Architecture

### Objective
Establish a clear, phased implementation plan before writing any production code.

### Decisions Made
- **No external dependencies** — The entire backend will use Python's standard library only.
- **In-memory firewall** — No `sudo` or `iptables` required; access control is simulated in-memory via `FirewallManager`.
- **Thread-safe shared state** — `SequenceTracker`, `FirewallManager`, and `Logger` will all use `threading.Lock()` for safe concurrent access.
- **Single-file frontend** — `frontend/index.html` will be completely self-contained with inline `<style>` and `<script>`.
- **Ports above 1024** — Default knock ports: `17000, 18000, 19000`; decoy/extra monitor ports: `17500, 18500`; service: `12222`; API/dashboard: `8080`.

### Architecture Overview

```
Client                      Server
  |                           |
  |-- knock port 17000 -----> |  (attempt 1)
  |-- knock port 18000 -----> |  (attempt 2)
  |-- knock port 19000 -----> |  (attempt 3 - sequence complete)
  |                           |  -> opens port 12222 for this IP
  |-- connect port 12222 ---> |  (protected service access granted)
  |                           |
```

### Component Responsibilities
| Component | File | Responsibility |
|---|---|---|
| Config | `config.json` | Central configuration (ports, timeouts, sequence) |
| Sequence Tracker | `server/sequence_tracker.py` | Per-IP knock state, timeout handling, sequence validation |
| Knock Server | `server/knock_server.py` | Multi-threaded TCP listeners on all knock ports |
| Firewall Manager | `server/firewall.py` | In-memory allow-list with TTL and expiry daemon |
| Protected Service | `server/service.py` | Minimal TCP echo service gated by firewall |
| Logger | `server/logger.py` | Structured JSON logging to disk + in-memory ring buffer |
| Client | `client/knock_client.py` | CLI tool to send knock sequence and connect |
| API Server | `server/api_server.py` | HTTP API (`/api/status`, `/api/sessions`, `/api/logs`, `/api/revoke`, `/api/knock`) |
| Dashboard | `frontend/index.html` | Real-time HTML/CSS/JS dashboard |
| Entry Point | `main.py` | Boots all components and keeps main thread alive |

### Final Project Structure
```
port-knocking/
├── config.json
├── main.py
├── project_report.md
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

### Phase 0 Results
- [x] Detailed phase breakdown created.
- [x] Architecture and component responsibilities documented.
- [x] Project structure defined.
- [x] `project_report.md` initialized.

---

## Phase 1 — Core Server: Port Monitor & Sequence Tracker

### Objective
Build the foundational server components that can listen on multiple ports and track per-IP knock attempts against a configured sequence.

### Files Created
- `config.json`
- `server/sequence_tracker.py`
- `server/knock_server.py`

### Design Details
#### `SequenceTracker`
- **State:** `dict[ip_str, {"progress": int, "last_time": float}]`
- **Locking:** `threading.Lock()` around all reads/writes to `self.sessions`.
- **Timeout logic:** If `now - last_time > timeout`, reset progress for that IP.
- **Failure logic:** If a wrong port is knocked, reset progress for that IP.
- **Success logic:** If `progress == len(expected_sequence)`, return `True`.

#### `knock_server.py`
- For each port in `config["knock_ports"]`:
  - Create a TCP socket, bind, listen.
  - Spawn a daemon thread.
  - On connection: extract client IP, close socket immediately, call `tracker.record_knock(ip, port)`.
  - If authenticated: call `firewall.open_port(ip)` and log `AUTH_SUCCESS`.
  - Otherwise: log `KNOCK_ATTEMPT` with current progress.

### Testing Approach
1. Start `knock_server.py` with a test config.
2. Use `nc` or a small script to knock ports in correct and incorrect order.
3. Verify tracker state via logs/assertions.

### Phase 1 Results
- [x] `config.json` created with default knock sequence `[7000, 8000, 9000]`, service port `2222`, monitor ports `[7000, 8000, 9000, 7500, 8500]`, timeout `10s`, access duration `30s`.
- [x] `server/sequence_tracker.py` implemented with thread-safe `threading.Lock()`, timeout handling, wrong-port reset, and progress tracking.
- [x] `server/knock_server.py` implemented with multi-threaded daemon listeners per knock port, immediate connection close, and event dispatching to `firewall`/`logger`.
- [x] **Unit tests passed** (`tests/test_sequence_tracker.py`):
  - Basic correct sequence → `True` on final knock.
  - Wrong first knock → no state stored.
  - Wrong mid-sequence → state reset.
  - Timeout exceeded → state reset on next knock.
  - Multiple IPs tracked independently.
  - `reset()` method clears state.
  - Progress reporting accurate (`1/3`, `2/3`, etc.).
- [x] **Smoke test passed** (`tests/test_knock_server.py`):
  - Started 4 knock listeners on `127.0.0.1`.
  - Sent correct sequence `7000→8000→9000` → `AUTH_SUCCESS` logged, `FakeFirewall.open_port` called.
  - Sent wrong sequence `7000→7500` → `AUTH_FAIL` logged, state reset.
- [x] All Python files pass `python3 -m py_compile` syntax verification.
- [x] Status: **Phase 1 Complete**

---

## Phase 2 — Firewall Manager & Protected Service

### Objective
Dynamically open and close access to a protected service port on a per-IP basis, and run a minimal service that respects those rules.

### Files Created
- `server/firewall.py`
- `server/service.py`

### Design Details
#### `FirewallManager`
- **State:** `dict[ip, expiry_timestamp]`
- **`open_port(ip)`:** Adds IP with expiry = `time.time() + access_duration`.
- **`is_allowed(ip)`:** Returns `True` only if IP exists and `time.time() < expiry`. Auto-removes expired entries.
- **`close_port(ip)`:** Explicitly removes IP from allowed set.
- **`get_active_sessions()`:** Returns list of dicts with `ip`, `expires_at`, `remaining_seconds`.
- **`start_expiry_daemon()`:** Background thread that sleeps 5 seconds, then prunes expired IPs and logs `PORT_CLOSED` for each.

#### `service.py`
- Binds to `config["service_port"]`.
- On each connection: checks `firewall.is_allowed(client_ip)`.
  - **Allowed:** Sends `"ACCESS GRANTED. Welcome, {ip}."`, then echoes any received data back.
  - **Denied:** Sends `"ACCESS DENIED."` and closes immediately.
- Logs `ACCESS_GRANTED` or `ACCESS_DENIED`.

### Testing Approach
1. Instantiate `FirewallManager` and manually call `open_port`.
2. Verify `is_allowed` returns `True`, then wait for expiry and verify `False`.
3. Connect to service before and after opening to verify gating.

### Phase 2 Results
- [x] `server/firewall.py` implemented with thread-safe `threading.Lock()`, in-memory allow-list, TTL expiry, manual close, and background expiry daemon.
- [x] `server/service.py` implemented as a minimal TCP echo service gated by `firewall.is_allowed()`, with proper banner and `ACCESS_GRANTED` / `ACCESS_DENIED` responses.
- [x] **Unit tests passed** (`tests/test_phase2.py`):
  - `test_firewall_basic`: `open_port` → `is_allowed=True`, wait for expiry → `is_allowed=False`.
  - `test_firewall_sessions`: Multiple IPs tracked; `get_active_sessions()` returns correct metadata with `remaining_seconds`.
  - `test_firewall_close_port`: Manual `close_port` immediately revokes access.
  - `test_firewall_expiry_daemon`: Daemon running every 5s successfully prunes expired entries.
  - `test_protected_service`: Service bound to `127.0.0.1:2222`; allowed client received `"ACCESS GRANTED. Welcome, 127.0.0.1."` and echo worked; denied client (after `close_port`) received `"ACCESS DENIED."`; `ACCESS_GRANTED` and `ACCESS_DENIED` events logged.
- [x] Status: **Phase 2 Complete**

---

## Phase 3 — Logger & Client

### Objective
Add structured logging (disk + in-memory) and a functional client for sending knock sequences.

### Files Created
- `server/logger.py`
- `client/knock_client.py`
- `logs/access.log` (generated at runtime)

### Design Details
#### `Logger`
- **Disk output:** Appends JSON lines to `log_file`.
- **In-memory buffer:** Keeps last 100 events in a `collections.deque(maxlen=100)`.
- **Format:** `{"timestamp": ISO8601, "event": str, "ip": str, "port": int|null, "message": str}`
- **Event types:** `KNOCK_ATTEMPT`, `AUTH_SUCCESS`, `AUTH_FAIL`, `ACCESS_GRANTED`, `ACCESS_DENIED`, `PORT_OPENED`, `PORT_CLOSED`.

#### `knock_client.py`
- `knock(host, port)`: Opens TCP connection and immediately closes.
- `run_knock_sequence(host, sequence, delay)`: Iterates sequence with `time.sleep(delay)`.
- `connect_to_service(host, service_port)`: Connects, prints banner, closes.
- **CLI usage:** `python client/knock_client.py [host]` (defaults to `127.0.0.1`).

### Testing Approach
1. Run client against local server; verify knock ports receive connections.
2. Check `logs/access.log` for structured JSON entries.
3. Verify `Logger.get_recent(n)` returns correct in-memory entries.

### Phase 3 Results
- [x] `server/logger.py` implemented with structured JSON line output to disk, `collections.deque(maxlen=100)` in-memory ring buffer, and `threading.Lock()` for thread safety.
- [x] `client/knock_client.py` implemented as a CLI tool with `knock()`, `run_knock_sequence()`, and `connect_to_service()` including an interactive echo prompt.
- [x] `client/__init__.py` created.
- [x] **End-to-end test passed** (`tests/test_phase3_e2e.py`):
  - Booted knock listeners (ports 7000, 7500, 8000, 9000), protected service (port 2222), real `Logger`, `FirewallManager`, and `SequenceTracker`.
  - **Test 1:** Direct service connection without knocking → `"ACCESS DENIED."` received.
  - **Test 2:** Correct knock sequence `7000→8000→9000` → `"ACCESS GRANTED. Welcome, 127.0.0.1."` received.
  - **Test 3:** Waited for `access_duration=5s` expiry → `"ACCESS DENIED."` received again.
  - **Log verification:** All expected event types present in `logs/test_access.log`:
    - `ACCESS_DENIED` (before knock)
    - `KNOCK_ATTEMPT` ×2 (progress 1/3, 2/3)
    - `AUTH_SUCCESS` (sequence complete)
    - `PORT_OPENED` (firewall opened)
    - `ACCESS_GRANTED` (service connection allowed)
    - `PORT_CLOSED` (expiry daemon cleaned up)
    - `ACCESS_DENIED` (after expiry)
- [x] Status: **Phase 3 Complete**

---

## Phase 4 — HTTP API for Frontend

### Objective
Expose server state and controls via a lightweight HTTP API using only Python stdlib.

### File Created
- `server/api_server.py`

### Design Details
- Built on `http.server.BaseHTTPRequestHandler`.
- Runs in a daemon thread on port `8080`.
- **CORS:** `Access-Control-Allow-Origin: *` on every response.
- **Static file serving:** `GET /` returns `frontend/index.html`.

### Endpoints
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/status` | Returns config snapshot (knock ports, service port, sequence) |
| GET | `/api/sessions` | Returns list of active allowed sessions |
| GET | `/api/logs?n=50` | Returns last `n` in-memory log entries |
| POST | `/api/revoke` | Body: `{"ip": "..."}` — manually revokes access |
| POST | `/api/knock` | Body: `{"host": "...", "sequence": [...]}` — triggers demo knock |

### Testing Approach
1. Start API server and use `curl` against each endpoint.
2. Verify JSON responses and correct CORS headers.
3. Test `POST /api/revoke` by checking subsequent service connection failures.

### Phase 4 Results
- [x] `server/api_server.py` implemented using `http.server.HTTPServer` + `BaseHTTPRequestHandler` with full CORS support (`Access-Control-Allow-Origin: *`, `OPTIONS` preflight).
- [x] **API endpoints verified** (`tests/test_phase4_api.py`):
  - `GET /api/status` → Returns `knock_ports`, `service_port`, `sequence` correctly.
  - `GET /api/sessions` → Returns 2 seeded active sessions with `ip`, `expires_at`, `remaining_seconds`.
  - `GET /api/logs?n=10` → Returns in-memory log entries including `KNOCK_ATTEMPT`, `PORT_OPENED`, `AUTH_SUCCESS`.
  - `POST /api/revoke` with `{"ip": "10.0.0.1"}` → Returns `{"ok": true}`, session count drops from 2 to 1.
  - `POST /api/knock` with `{"host": "127.0.0.1", "sequence": [7000]}` → Returns `{"ok": true}` after sending TCP knock.
  - `GET /` → Returns `frontend/index.html` when present (verified 404 before Phase 5, as expected).
- [x] Status: **Phase 4 Complete**

---

## Phase 5 — Frontend Dashboard

### Objective
Build a self-contained, real-time dashboard for monitoring and interacting with the port knocking system.

### File Created
- `frontend/index.html`

### Design Details
- **Theme:** Dark terminal-inspired (dark background, green/cyan accents, monospace font).
- **Layout:** CSS Grid with 3 panels.
  - **Status Panel:** Displays knock sequence, service port, monitored knock ports.
  - **Active Sessions Panel:** Table with columns IP, Expires At, Remaining (countdown), Revoke button.
  - **Live Log Panel:** Scrollable list, color-coded by event type.
- **Interactivity:**
  - Auto-refresh every 3 seconds via `setInterval` polling `/api/logs` and `/api/sessions`.
  - Revoke button → `POST /api/revoke`.
  - Simulate Knock form → `POST /api/knock`.
- **Color Coding:**
  - `AUTH_SUCCESS` → green
  - `ACCESS_DENIED` / `AUTH_FAIL` → red
  - `KNOCK_ATTEMPT` → yellow
  - `PORT_OPENED` / `PORT_CLOSED` → cyan
  - Others → white/grey

### Testing Approach
1. Open dashboard in browser.
2. Trigger knock sequence and verify live log updates and session table appears.
3. Wait for timeout and verify session disappears.
4. Click Revoke and verify session disappears immediately.

### Phase 5 Results
- [x] `frontend/index.html` created as a single self-contained file (8079 bytes) with inline `<style>` and `<script>`.
- [x] **Dashboard features implemented:**
  - Dark terminal-inspired theme (`#0d1117` background, monospace font, green/cyan accents).
  - **Status Panel:** Displays knock sequence (`7000 → 8000 → 9000`), service port (`2222`), and monitored ports as badges.
  - **Active Sessions Panel:** Table with IP, Expires At, Remaining Seconds, and **Revoke** button per row.
  - **Live Log Panel:** Scrollable reverse-chronological list with color-coded events:
    - `AUTH_SUCCESS` / `ACCESS_GRANTED` → green
    - `ACCESS_DENIED` / `AUTH_FAIL` → red
    - `KNOCK_ATTEMPT` → yellow
    - `PORT_OPENED` / `PORT_CLOSED` → cyan
  - **Simulate Knock** form in Status Panel → calls `POST /api/knock`.
  - Auto-refresh every 3 seconds via `setInterval` polling `/api/logs` and `/api/sessions`.
  - `escapeHtml()` helper prevents XSS in log and session rendering.
- [x] **Verification:** Re-ran `tests/test_phase4_api.py`; `GET /` now successfully serves `frontend/index.html` (8079 bytes) instead of 404.
- [x] Status: **Phase 5 Complete**

---

## Phase 6 — Integration & Entry Point

### Objective
Wire all components into a single runnable entry point and perform end-to-end validation.

### File Created
- `main.py`

### Design Details
- Loads `config.json`.
- Instantiates `Logger`, `FirewallManager`, `SequenceTracker`.
- Starts:
  1. Firewall expiry daemon.
  2. Knock port listeners (daemon threads internally).
  3. Protected service (daemon thread).
  4. HTTP API server (daemon thread).
- Prints startup messages with URLs/ports.
- Keeps main thread alive with `threading.Event().wait()`.
- **Graceful error handling:** Catches `OSError` for port conflicts, logs a clear message, and exits cleanly.

### End-to-End Test Plan
1. Run `python main.py`.
2. Open `http://localhost:8080` in browser (dashboard loads).
3. Run `python client/knock_client.py` (or use dashboard Simulate Knock).
4. **Verify:**
   - Log panel shows `KNOCK_ATTEMPT` entries with progress.
   - Final knock triggers `AUTH_SUCCESS` and `PORT_OPENED`.
   - Session appears in Active Sessions with countdown.
   - Client connects to service and receives `"ACCESS GRANTED..."`.
5. **Verify denial:**
   - Connect to service without knocking → `ACCESS DENIED`.
   - Knock wrong sequence → `AUTH_FAIL`, progress resets.
6. **Verify expiry/revoke:**
   - Wait for `access_duration` → session auto-removes, `PORT_CLOSED` logged.
   - Or click Revoke → session removed immediately.

### Phase 6 Results
- [x] `main.py` implemented as the single entry point wiring `Logger`, `FirewallManager`, `SequenceTracker`, `start_knock_listeners`, `start_protected_service`, and `start_api_server`.
- [x] Graceful error handling for `config.json` load failures and `OSError` on port binding.
- [x] KeyboardInterrupt (`Ctrl+C`) gracefully shuts down the expiry daemon.
- [x] **Full integration test passed** (`tests/test_phase6_integration.py`):
  - Booted 5 knock listeners (7000, 8000, 9000, 7500, 8500), protected service (2222), API server (8080), expiry daemon, and real logger.
  - **Test A:** `GET /api/status` returns correct sequence and service port.
  - **Test B:** `POST /api/knock` triggers sequence → 1 active session created.
  - **Test C:** Service connection → `"ACCESS GRANTED. Welcome, 127.0.0.1."` received.
  - **Test D:** Full event chain verified in logs: `KNOCK_ATTEMPT` → `AUTH_SUCCESS` → `PORT_OPENED` → `ACCESS_GRANTED`.
  - **Test E:** `POST /api/revoke` → session count drops to 0.
  - **Test F:** Service connection after revoke → `"ACCESS DENIED."` received.
  - **Test G:** Waited for `access_duration=5s` expiry → expiry daemon pruned session, count 0.
- [x] **Syntax verification:** `python3 -m py_compile main.py` passed.
- [x] Status: **Phase 6 Complete — Project Ready**

---

## Bug Fix: Port 7000 Conflict on macOS

### Issue
When running `main.py` on macOS, the frontend dashboard's **Simulate Knock** button appeared to fail silently for the first port in the sequence. Logs showed `AUTH_FAIL` for ports 8000 and 9000, but no `KNOCK_ATTEMPT` for port 7000.

### Root Cause
macOS **ControlCe** (Control Center) binds to port **7000** (`afs3-fileserver`). When `knock_server.py` tried to bind to `0.0.0.0:7000`, it failed with `Address already in use`. The first knock in the sequence never reached the server, so subsequent knocks on 8000 and 9000 were treated as wrong first attempts → `AUTH_FAIL`.

### Fix
1. **Changed default ports** in `config.json` from `7000/8000/9000/7500/8500/2222` to `17000/18000/19000/17500/18500/12222` to avoid system service conflicts.
2. **Added `time.sleep(0.05)`** in `api_server.py`'s `_demo_knock()` after `connect()` and before `close()` to give the server a moment to process the connection.
3. **Added `import time`** to `api_server.py`.

### Verification
Ran `tests/test_final_e2e.py` with the new port configuration:
- All 5 knock listeners bound successfully.
- Frontend `POST /api/knock` produced the correct event chain:
  - `KNOCK_ATTEMPT` (17000) — Progress 1/3
  - `KNOCK_ATTEMPT` (18000) — Progress 2/3
  - `AUTH_SUCCESS` (19000) — Sequence complete
  - `PORT_OPENED` (12222) — Access granted
- 1 active session created for `127.0.0.1`.
- Service connection returned `"ACCESS GRANTED. Welcome, 127.0.0.1."`.
- Revoke via API immediately denied subsequent connections.

---

## Feature Additions — Dynamic Sequence Config & Port Connection Tester

### Objective
Add two interactive dashboard features:
1. **Custom Knock Sequence** — allow the user to define their own knock sequence via the frontend, with real-time port availability checking.
2. **Port Connection Tester** — allow the user to manually enter any port and test connectivity from the backend, with results shown in the Live Log terminal.

### Files Modified
- `server/knock_server.py` — added `_active_sockets` registry, `stop_knock_listeners()`, `restart_knock_listeners()`, and `is_port_free()` (strict, no `SO_REUSEADDR`).
- `server/api_server.py` — added `POST /api/config/sequence` and `POST /api/test-port` endpoints; updated `make_handler` and `start_api_server` signatures to accept `tracker`.
- `main.py` — updated `start_api_server` call to pass `tracker`.
- `frontend/index.html` — added "Custom Sequence" form and "Test Port Connection" form with toast notifications.

### New API Endpoints
| Method | Path | Body | Response |
|--------|------|------|----------|
| POST | `/api/config/sequence` | `{"sequence": [21000, 22000, 23000]}` | `{"ok": true}` or `{"ok": false, "occupied_ports": [...]}` |
| POST | `/api/test-port` | `{"port": 2000, "host": "127.0.0.1"}` | `{"ok": true, "connected": true/false, "message": "..."}` |

### Design Details
#### Dynamic Sequence Update
- Parses comma-separated ports from frontend input.
- Validates all ports are integers `> 1024`.
- Checks each port for availability using a temporary socket bind **without** `SO_REUSEADDR` (strict conflict detection).
- Exempts ports already owned by the current knock listeners so reuse is allowed.
- If any port is occupied by another process, returns HTTP `409` with the specific occupied port(s).
- If all free, updates `config["knock_sequence"]`, `config["knock_ports"]`, `tracker.expected_sequence`, stops old listeners, and starts new ones.
- Logs `CONFIG_UPDATE` event.

#### Port Connection Tester
- Accepts a port number (and optional host, default `127.0.0.1`).
- Opens a TCP connection from the backend to the target.
- If the target is a knock port, the existing `knock_server` naturally records it as a `KNOCK_ATTEMPT`, `AUTH_SUCCESS`, or `AUTH_FAIL`.
- Returns connection result to frontend, which shows a toast notification.
- Live Log auto-refreshes and displays the knock/auth events just like normal knocks.

### Frontend Changes
- **Custom Sequence** form in Status Panel:
  - Text input with placeholder `e.g. 20000,30000,40000`
  - "Update Sequence" button
  - On occupied ports: red toast with specific port numbers
  - On success: green toast with new sequence, Status panel auto-refreshes
- **Test Port Connection** form in Status Panel:
  - Number input with placeholder `e.g. 2000`
  - Supports Enter key submission
  - "Test" button
  - Green toast on successful connection, red toast on failure
  - Live Log naturally shows `KNOCK_ATTEMPT` / `AUTH_SUCCESS` / `AUTH_FAIL` for knock ports

### Testing
- `tests/test_new_features.py`:
  - **Feature 1a:** Updated sequence to `[21000, 22000, 23000]` → all free, listeners restarted, status API reflects new sequence.
  - **Feature 1b:** Attempted update to `[8080, 22000, 23000]` → port `8080` correctly detected as occupied (API server running), returned `occupied_ports: [8080]` with clear error message.
  - **Feature 2a:** Tested port `21000` → connection succeeded, `KNOCK_ATTEMPT` appeared in Live Log.
  - **Feature 2b:** Tested ports `22000` then `23000` → full sequence completed, `AUTH_SUCCESS` and `PORT_OPENED` logged, 1 active session created.
  - **Feature 2c:** Tested port `9999` → connection refused, failure toast shown.
  - **Feature 2d:** Knocked `21000→22000→21000` (wrong last port) → `AUTH_FAIL` logged, sequence reset.
- All existing tests (`test_phase4_api.py`, `test_phase6_integration.py`, `test_final_e2e.py`) re-run and passed with no regressions.

### Results
- [x] `server/knock_server.py` updated with listener lifecycle management (`stop` / `restart`).
- [x] `server/api_server.py` updated with `POST /api/config/sequence` and `POST /api/test-port`.
- [x] `frontend/index.html` updated with two new forms and toast notifications (10881 bytes).
- [x] Strict port conflict detection implemented (no `SO_REUSEADDR` in `is_port_free`).
- [x] Existing ports exempted from conflict check to allow sequence modifications.
- [x] Status: **New Features Complete & Tested**

---

## Final Summary

All 6 phases have been successfully implemented and tested:

| Phase / Feature | Component | Test Result |
|-----------------|-----------|-------------|
| 1 | Sequence Tracker + Knock Server | ✅ 7 unit tests + smoke test |
| 2 | Firewall Manager + Protected Service | ✅ 4 unit tests + echo test |
| 3 | Logger + Client | ✅ End-to-end knock→auth→service flow |
| 4 | HTTP API | ✅ All 5 endpoints + CORS + static file serving |
| 5 | Frontend Dashboard | ✅ Served at `/`, all panels functional |
| 6 | Integration (`main.py`) | ✅ Full system integration test passed |
| — | Dynamic Sequence Config | ✅ Port availability check + listener restart |
| — | Port Connection Tester | ✅ Manual per-port knock with live log feedback |

**To run the system:**
```bash
python3 main.py
```

**To use the client:**
```bash
python3 client/knock_client.py [host]
```

**Dashboard URL:** http://localhost:8080/  
*(Now includes Custom Sequence config and Port Connection Tester forms)*

---

## Appendix: Final Project Structure

```
port-knocking/
├── config.json                 # Central configuration
├── main.py                     # Entry point — boots all components
├── project_report.md           # This report — updated after every phase
├── server/
│   ├── __init__.py
│   ├── knock_server.py         # Multi-threaded knock port listeners (with restart)
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
│   └── test_new_features.py    # Dynamic sequence + port tester tests
└── logs/
    └── access.log              # Runtime structured logs
```

## Appendix: Configuration

### `config.json`
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

> **Note:** The default ports were changed from `7000/8000/9000` to `17000/18000/19000` because macOS ControlCe occupies port 7000. You can customize these freely in `config.json` as long as they are above 1024 and not in use by your OS.

---

*Report will be updated incrementally as each phase is implemented.*

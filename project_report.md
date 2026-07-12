# Project Documentation: Dynamic Firewall Authentication System with Port Knocking, IPS, TOTP, and GeoIP

## 1. Objective
The primary objective of this project is to develop and demonstrate an advanced, multi-layered Dynamic Firewall Authentication System. This system enhances traditional perimeter security by obscuring access to critical services (e.g., SSH, databases) until a specific sequence of network interactions (port knocks) is successfully executed by the client. The project also aims to showcase how traditional port knocking can be fortified against modern attacks using intrusion prevention mechanisms, time-based authentication, and geographic filtering.

## 2. Problem Statement
Traditional static firewalls and open ports present a continuous attack surface for malicious actors employing automated scanners (e.g., Nmap) and brute-force tools. Even with strong passwords or key-based authentication, an exposed service port remains vulnerable to zero-day exploits and volumetric attacks. 
Standard port knocking mitigates this by keeping ports closed by default, but it suffers from replay attacks, blind brute-forcing, and a lack of contextual awareness. There is a need for a dynamic authentication system that not only obscures services but actively defends against active enumeration and adapts to modern security paradigms.

## 3. Methodology
To solve the aforementioned problems, the project implements a base port knocking daemon and progressively enhances it through four distinct modes (methodologies):

1. **Original Mode (Base Port Knocking):** The firewall dynamically opens a protected service port only after a client connects to a predefined, ordered sequence of "knock" ports within a specific time window.
2. **IPS Mode (Intrusion Prevention System):** Introduces a strike-based penalty system. Any connection to an incorrect port in the sequence acts as a strike. Reaching a threshold automatically bans the offending IP, preventing brute-force sequence guessing.
3. **TOTP Mode (Time-Based One-Time Sequences):** Eliminates replay attacks by rotating the required knock sequence every 30 seconds, conceptually similar to an authenticator app, synchronized via a shared secret between client and server.
4. **GeoIP Mode (Location-based Filtering):** Adds a contextual layer by evaluating the geographical origin of the client's IP address against a whitelist or blacklist before allowing the sequence to begin, mitigating distributed international attacks.

## 4. Results
The implemented system successfully obscures the protected service from unauthorized network scans. The addition of the IPS module effectively neutralizes brute-force attempts within seconds. The TOTP implementation ensures that intercepted knock sequences become useless immediately after the time window expires. The GeoIP filtering accurately drops traffic originating from disallowed regions at the firewall edge. The dashboard provides real-time, visual confirmation of these mechanisms in action, demonstrating a highly resilient dynamic firewall architecture.

## 5. Conclusion
This project successfully demonstrates that while traditional port knocking is a useful obscurity technique, it must be augmented to provide true security. By integrating IPS, TOTP, and GeoIP modules, the system evolves into a robust, context-aware, and dynamic authentication layer. This architecture provides a significant defense-in-depth capability, dramatically reducing the attack surface of critical network infrastructure.

---

## 6. Technical Knowledge & Codebase Mapping

The codebase is organized into a modular architecture, with a base framework and distinct directories for each advanced demo mode.

### Directory Structure & Functionality

*   **`/server/`**: Contains the core logic for the **Original** port knocking implementation.
    *   `api_server.py`: Runs a `ThreadingHTTPServer` to serve the REST API for the dashboard, handling configuration updates, session retrievals, and manual overrides.
    *   `knock_server.py`: Manages the TCP socket listeners for the knock ports. It spawns threads to listen for incoming connections and passes the client IP to the sequence tracker.
    *   `sequence_tracker.py`: Maintains the state of knocking progress for each IP. It verifies if a knock is correct, advances the state, handles timeouts, and resets on failure.
    *   `firewall.py`: Simulates (or executes) the actual firewall rules (e.g., iptables commands) to grant or revoke access to the protected service port.
    *   `logger.py`: Centralized logging module that records events (attempts, successes, bans) to feed into the frontend dashboard's live log view.
*   **`/demo_ips/server/`**: Contains the modified backend for the **IPS** mode.
    *   `sequence_tracker.py` is augmented here to track "strikes" for incorrect knocks and maintain a list of banned IPs with expiration timestamps.
*   **`/demo_totp/server/`**: Contains the modified backend for the **TOTP** mode.
    *   Integrates time-based cryptographic hashing (HMAC-SHA) to dynamically alter the `knock_sequence` array every 30 seconds based on a predefined port pool.
*   **`/demo_geoip/server/`**: Contains the modified backend for the **GeoIP** mode.
    *   Integrates IP-to-location lookup logic, intercepting knocks and discarding them if the country/region code is not within the permitted configuration list.
*   **`/frontend/`**: Contains the HTML/CSS/JS for the dashboards.
    *   `index.html`: The base Original dashboard UI.
    *   `ips.html`, `totp.html`, `geoip.html`: The specialized dashboards injected with extra panels (e.g., Strike Monitors, TOTP countdowns) via the generation script.
*   **`generate_dashboards_v2.py`**: A build script that takes the base `index.html` and injects specific JS, HTML, and CSS to generate the specialized UI dashboards for each demo mode.
*   **`run_all_demos.sh`**: The orchestrator script that launches all four Python backends on different local ports simultaneously.

---

## 7. Technology Stack

*   **Backend:** Python 3.x
*   **Concurrency:** `threading` module, `http.server.ThreadingHTTPServer`
*   **Networking:** Python `socket` library (TCP implementation)
*   **Frontend UI:** HTML5, Vanilla JavaScript (ES6), CSS3 (Custom properties, CSS Grid, Flexbox, Micro-animations)
*   **Communication:** RESTful HTTP APIs with JSON payloads, `fetch` API on the client.

---

## 8. Implementation Details (Rebuilding from Scratch)

If you were to rewrite this system from scratch, follow this blueprint:

1.  **Define the Data Structures (State Management):**
    *   Create a thread-safe dictionary (using mutex locks) mapping `Client IP -> { current_step, last_knock_timestamp }`.
2.  **Implement the Listeners:**
    *   For each port in the sequence, bind a TCP `socket`. Do not use `accept()` to establish a full connection payload; simply accept the SYN, grab the remote IP address, and instantly close the socket (RST/FIN).
3.  **Process the Knock:**
    *   When IP `X` hits port `Y`, check the dictionary. If `Y` is the expected next port, increment `current_step`. Update `last_knock_timestamp`.
    *   If `Y` is incorrect, delete IP `X` from the dictionary (reset sequence).
    *   If `now() - last_knock_timestamp > timeout`, delete IP `X` from the dictionary.
4.  **Firewall Action:**
    *   If `current_step == len(sequence)`, trigger the firewall action. Execute a system command (e.g., `iptables -A INPUT -s {IP} -p tcp --dport 22 -j ACCEPT`) and spawn a timer thread to remove the rule after `N` seconds.
5.  **Build the API:**
    *   Use `ThreadingHTTPServer` to expose endpoints like `GET /api/status`, `GET /api/logs`, `POST /api/knock` (which simulates a client connecting to the ports sequentially).
6.  **Build the UI:**
    *   Use CSS Grid to create a responsive layout. Poll the `/api/status`, `/api/sessions`, and `/api/logs` every second using `setInterval` and `fetch`. Render the returned JSON directly into the DOM.
7.  **Enhance Modules:**
    *   **IPS:** Add a `strikes` dictionary. If step 3 triggers a reset, increment strikes. If strikes > 3, add IP to `banned` dictionary. Drop all subsequent packets from `banned` IPs.
    *   **TOTP:** Write a loop that runs every 30 seconds. Calculate `HMAC_SHA256(secret, floor(unix_time / 30))`. Use the resulting hash bytes to modulo-select ports from a pool. Update the required sequence.
    *   **GeoIP:** Before step 3, query a local GeoLite2 database or an API with the IP. If country != "US", return early.

---

## 9. Architectural Decisions & Novelty

### Architectural Decisions
*   **Threaded HTTP Server:** Upgraded from the base `HTTPServer` to `ThreadingHTTPServer` to handle the asynchronous polling nature of the frontend dashboard without blocking.
*   **Decoupled Listeners:** Knock ports are monitored by entirely independent, lightweight threads listening on raw sockets. This prevents a slow-loris attack on a specific port from delaying the sequence tracker.
*   **In-Memory State:** All state (sessions, bans, sequence progress) is kept in memory. This is a deliberate choice for speed (sub-millisecond validation) and simplicity in a demo environment, avoiding database I/O latency.
*   **Vanilla JS Frontend:** Avoided heavy frameworks (React/Vue) in favor of Vanilla JS to keep the codebase transparent, portable, and easily modifiable via string-injection scripts (`generate_dashboards_v2.py`).

### Claimable Novelty Points
1.  **Dynamic Honey-Ports (IPS Integration):** Instead of merely ignoring incorrect knocks, the system turns all non-sequence ports into active honeypots. Touching them weaponizes the firewall against the scanner immediately.
2.  **Time-Synchronized Port Hopping (TOTP Integration):** Applying 2FA/TOTP concepts to network port sequences creates a moving target, effectively solving the traditional port knocking vulnerability to packet sniffing and replay attacks.
3.  **Real-time Visualization Engine:** A decoupled, polling-based visualization layer provides sub-second insight into the ephemeral state of the firewall, visualizing concepts (like strikes and TTLs) that are normally invisible.

---

## 10. Steps to Run the Project

1.  **Prerequisites:** Python 3.7+ installed. No external pip dependencies are strictly required for the core daemon (uses standard library `socket`, `http`, `threading`).
2.  **Generate Dashboards:** 
    ```bash
    python3 generate_dashboards_v2.py
    ```
    *(This script compiles the UI configurations for all modules.)*
3.  **Launch All Demos:**
    ```bash
    ./run_all_demos.sh
    ```
    This script will spawn the four backend servers in the background.
4.  **Access the Hub:** Open a web browser and navigate to `http://localhost:8084` to access the main hub.

---

## 11. Walkthrough and Using the Demos (Network Concepts)

When you access the dashboards, you will see a UI split into Controls, Status, Sessions, and Live Logs. Here is what happens in each mode conceptually:

### A. Original Mode (Dashboard: `http://localhost:8084/dashboard`)
*   **Concept:** Standard sequence knocking.
*   **Network Event:** When you click "Simulate Knock", the frontend makes a POST request to the API. The API triggers a local function that sequentially opens a TCP SYN connection to the predefined ports (e.g., 47000, 48000, 49000). The socket listener on the backend detects the SYN, records the IP, and drops the connection. Once the third SYN arrives in order, the daemon virtually "opens" the service port (42225) and grants a 30s session TTL.

### B. IPS Mode (Dashboard: `http://localhost:8081`)
*   **Concept:** Active Defense and Intrusion Prevention.
*   **Network Event:** You have two buttons: "Send Wrong Knock" and "Send Correct Knock". 
    *   If you send a wrong knock (e.g., 29000), the backend listener detects a TCP connection on an unexpected port. It logs a strike for your IP.
    *   Upon reaching 3 strikes, the API transitions your IP to a "Banned" state. 
    *   If you try to send the "Correct Knock" while banned, the backend immediately drops the request. In a real network, this translates to the kernel automatically sending TCP RST (Reset) packets to the banned IP via iptables `DROP`/`REJECT` rules before the knock daemon even sees them.

### C. TOTP Mode (Dashboard: `http://localhost:8082`)
*   **Concept:** Cryptographic Port Hopping.
*   **Network Event:** You will see a progress bar ticking down from 30 seconds. In the background, the server computes a new HMAC hash. When the timer hits zero, the server closes the old sockets and binds to a completely new set of ports dictated by the hash. 
    *   If an attacker recorded your knock sequence at `T=10s` and replays those same TCP SYN packets at `T=35s`, the packets will hit closed ports (Connection Refused), because the correct ports have seamlessly migrated.

### D. GeoIP Mode (Dashboard: `http://localhost:8083`)
*   **Concept:** Layer 3 / Layer 4 Contextual Filtering.
*   **Network Event:** Before the `sequence_tracker` even registers the TCP SYN packet, the `api_server` checks the incoming IP against a GeoIP lookup (simulated in the demo based on predefined IP blocks). 
    *   If the IP resolves to an unauthorized geographic region, the knock is silently discarded (blackholed). In the UI log, you will visually see the location badge flagged red, illustrating how edge-routing logic can preemptively filter traffic before authentication logic is even invoked.

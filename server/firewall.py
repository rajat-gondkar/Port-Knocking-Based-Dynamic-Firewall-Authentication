import threading
import time
from typing import Dict, List, Optional
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from server.logger import Logger


class FirewallManager:
    """
    In-memory firewall manager (no root required).
    Optionally extend to real iptables.
    """

    def __init__(self, service_port: int, access_duration: int, logger: Optional["Logger"] = None):
        """
        :param service_port: The protected service port (informational).
        :param access_duration: Seconds an IP remains allowed after open_port().
        :param logger: Logger instance for PORT_OPENED / PORT_CLOSED events.
        """
        self.service_port = service_port
        self.access_duration = access_duration
        self.logger = logger
        self.allowed_ips: Dict[str, float] = {}
        self.lock = threading.Lock()
        self._stop_daemon = threading.Event()
        self._daemon_thread: Optional[threading.Thread] = None

    def open_port(self, ip: str):
        """Add IP to allowed set with expiry = now + access_duration. Log the action."""
        with self.lock:
            expiry = time.time() + self.access_duration
            self.allowed_ips[ip] = expiry
        if self.logger:
            self.logger.log("PORT_OPENED", ip, self.service_port, f"Access granted for {self.access_duration}s")

    def close_port(self, ip: str):
        """Remove IP from allowed set. Log the action."""
        with self.lock:
            removed = self.allowed_ips.pop(ip, None)
        if removed and self.logger:
            self.logger.log("PORT_CLOSED", ip, self.service_port, "Access revoked")

    def is_allowed(self, ip: str) -> bool:
        """Return True if IP is in allowed set and not expired. Auto-expire if past time."""
        with self.lock:
            expiry = self.allowed_ips.get(ip)
            if expiry is None:
                return False
            if time.time() > expiry:
                self.allowed_ips.pop(ip, None)
                if self.logger:
                    self.logger.log("PORT_CLOSED", ip, self.service_port, "Expired")
                return False
            return True

    def get_active_sessions(self) -> List[dict]:
        """Return list of {ip, expires_at, remaining_seconds} for all active IPs."""
        now = time.time()
        sessions = []
        with self.lock:
            # Prune expired entries while iterating
            expired = []
            for ip, expiry in list(self.allowed_ips.items()):
                if now > expiry:
                    expired.append(ip)
                    continue
                sessions.append({
                    "ip": ip,
                    "expires_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(expiry)),
                    "remaining_seconds": int(expiry - now)
                })
            for ip in expired:
                self.allowed_ips.pop(ip, None)
                if self.logger:
                    self.logger.log("PORT_CLOSED", ip, self.service_port, "Expired")
        return sessions

    def start_expiry_daemon(self):
        """Background thread: every 5 seconds, prune expired IPs."""
        def _daemon():
            while not self._stop_daemon.is_set():
                self._stop_daemon.wait(5)
                self.get_active_sessions()  # side-effect: prunes expired

        self._daemon_thread = threading.Thread(target=_daemon, daemon=True, name="FirewallExpiryDaemon")
        self._daemon_thread.start()

    def stop_expiry_daemon(self):
        """Signal the expiry daemon to stop."""
        self._stop_daemon.set()

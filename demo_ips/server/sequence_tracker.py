import threading
import time
from typing import Dict, Any


class SequenceTracker:
    """
    Manages per-IP knock state for port-knocking authentication.
    Thread-safe using threading.Lock.
    """

    def __init__(self, expected_sequence: list[int], timeout: int):
        """
        :param expected_sequence: List of ports in the correct knock order.
        :param timeout: Maximum seconds between consecutive knocks before reset.
        """
        self.expected_sequence = expected_sequence
        self.timeout = timeout
        self.sessions: Dict[str, Dict[str, Any]] = {}
        
        # --- IPS ADDITIONS ---
        self.strikes: Dict[str, int] = {}
        self.banned_ips: Dict[str, float] = {}
        self.ban_duration = 300  # 5 minutes
        self.max_strikes = 3
        # ---------------------
        
        self.lock = threading.Lock()

    def record_knock(self, ip: str, port: int, logger=None) -> bool:
        """
        Record a knock attempt from `ip` on `port`.
        Returns True if authenticated.
        """
        with self.lock:
            now = time.time()
            
            # --- IPS ADDITIONS ---
            # Check if banned
            if ip in self.banned_ips:
                if now > self.banned_ips[ip]:
                    # Ban expired
                    del self.banned_ips[ip]
                    self.strikes.pop(ip, None)
                    if logger:
                        logger.log("BAN_LIFTED", ip, port, "Ban duration expired")
                else:
                    # Still banned
                    return False
            # ---------------------

            session = self.sessions.get(ip)

            if session is None:
                # First knock from this IP
                if port == self.expected_sequence[0]:
                    self.sessions[ip] = {
                        "progress": 1,
                        "last_time": now
                    }
                    return False
                else:
                    self._add_strike(ip, now, logger)
                    return False

            # Check timeout
            if now - session["last_time"] > self.timeout:
                self.sessions.pop(ip, None)
                self._add_strike(ip, now, logger, reason="Timeout exceeded")
                # Re-evaluate as fresh knock
                if port == self.expected_sequence[0] and ip not in self.banned_ips:
                    self.sessions[ip] = {
                        "progress": 1,
                        "last_time": now
                    }
                return False

            expected_port = self.expected_sequence[session["progress"]]

            if port == expected_port:
                session["progress"] += 1
                session["last_time"] = now

                if session["progress"] == len(self.expected_sequence):
                    # Sequence complete — authenticate and clear state
                    self.sessions.pop(ip, None)
                    self.strikes.pop(ip, None)  # Reset strikes on success
                    return True
                return False
            else:
                # Wrong port — reset progress
                self.sessions.pop(ip, None)
                self._add_strike(ip, now, logger, reason="Incorrect sequence")
                return False

    def _add_strike(self, ip: str, now: float, logger=None, reason="Invalid knock"):
        """Helper to add a strike and check for ban."""
        self.strikes[ip] = self.strikes.get(ip, 0) + 1
        strike_count = self.strikes[ip]
        if logger:
            logger.log("STRIKE", ip, None, f"{reason}. Strike {strike_count}/{self.max_strikes}")
            
        if strike_count >= self.max_strikes:
            self.banned_ips[ip] = now + self.ban_duration
            self.sessions.pop(ip, None)
            if logger:
                logger.log("IP_BANNED", ip, None, f"Banned for {self.ban_duration}s due to too many strikes")

    def reset(self, ip: str):
        """Clear knock state for an IP."""
        with self.lock:
            self.sessions.pop(ip, None)

    def get_progress(self, ip: str) -> str:
        """
        Return current progress string like '2/3' for the given IP.
        """
        with self.lock:
            session = self.sessions.get(ip)
            if session is None:
                return f"0/{len(self.expected_sequence)}"
            return f"{session['progress']}/{len(self.expected_sequence)}"
            
    def get_bans(self) -> list:
        now = time.time()
        bans = []
        with self.lock:
            for ip, expiry in list(self.banned_ips.items()):
                if now > expiry:
                    del self.banned_ips[ip]
                    self.strikes.pop(ip, None)
                else:
                    bans.append({
                        "ip": ip,
                        "strikes": self.strikes.get(ip, self.max_strikes),
                        "expires_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(expiry)),
                        "remaining_seconds": int(expiry - now)
                    })
        return bans

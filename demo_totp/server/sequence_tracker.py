import threading
import time
import random
from typing import Dict, Any


class SequenceTracker:
    """
    Manages per-IP knock state for port-knocking authentication.
    Thread-safe using threading.Lock.
    """

    def __init__(self, expected_sequence: list[int], timeout: int):
        self.timeout = timeout
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.lock = threading.Lock()
        
        # --- TOTP ADDITIONS ---
        self.pool = [37000, 37100, 37200, 37300, 37400, 37500, 37600, 37700, 37800, 37900]
        self.totp_interval = 30  # seconds
        # ---------------------
        
    def get_current_sequence(self):
        """Generate a deterministic sequence based on the current time window."""
        window = int(time.time() // self.totp_interval)
        random.seed(window)
        return random.sample(self.pool, 3)
        
    def get_totp_state(self):
        """Return the current sequence and seconds remaining in the interval."""
        now = time.time()
        remaining = self.totp_interval - (now % self.totp_interval)
        return {
            "sequence": self.get_current_sequence(),
            "remaining_seconds": int(remaining)
        }

    def record_knock(self, ip: str, port: int) -> bool:
        with self.lock:
            now = time.time()
            session = self.sessions.get(ip)
            
            # The expected sequence might change between knocks.
            # But usually we validate against the *current* window.
            # To be lenient, we could check the previous window, but let's be strict for the demo.
            current_expected_sequence = self.get_current_sequence()

            if session is None:
                if port == current_expected_sequence[0]:
                    self.sessions[ip] = {
                        "progress": 1,
                        "last_time": now
                    }
                return False

            if now - session["last_time"] > self.timeout:
                self.sessions.pop(ip, None)
                if port == current_expected_sequence[0]:
                    self.sessions[ip] = {
                        "progress": 1,
                        "last_time": now
                    }
                return False

            expected_port = current_expected_sequence[session["progress"]]

            if port == expected_port:
                session["progress"] += 1
                session["last_time"] = now

                if session["progress"] == len(current_expected_sequence):
                    self.sessions.pop(ip, None)
                    return True
                return False
            else:
                self.sessions.pop(ip, None)
                return False

    def reset(self, ip: str):
        with self.lock:
            self.sessions.pop(ip, None)

    def get_progress(self, ip: str) -> str:
        with self.lock:
            session = self.sessions.get(ip)
            if session is None:
                return "0/3"
            return f"{session['progress']}/3"

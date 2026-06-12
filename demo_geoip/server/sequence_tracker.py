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
        self.lock = threading.Lock()

    def record_knock(self, ip: str, port: int) -> bool:
        """
        Record a knock attempt from `ip` on `port`.

        - If port matches the next expected port in sequence, advance progress.
        - If progress completes the full sequence, return True (authenticated).
        - If timeout exceeded since last knock, reset progress for that IP.
        - If wrong port knocked, reset progress for that IP.
        - Returns False in all non-completion cases.
        """
        with self.lock:
            now = time.time()
            session = self.sessions.get(ip)

            if session is None:
                # First knock from this IP
                if port == self.expected_sequence[0]:
                    self.sessions[ip] = {
                        "progress": 1,
                        "last_time": now
                    }
                # Wrong first port — no state stored
                return False

            # Check timeout
            if now - session["last_time"] > self.timeout:
                self.sessions.pop(ip, None)
                # Re-evaluate as fresh knock
                if port == self.expected_sequence[0]:
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
                    return True
                return False
            else:
                # Wrong port — reset progress
                self.sessions.pop(ip, None)
                return False

    def reset(self, ip: str):
        """Clear knock state for an IP."""
        with self.lock:
            self.sessions.pop(ip, None)

    def get_progress(self, ip: str) -> str:
        """
        Return current progress string like '2/3' for the given IP.
        Returns '0/N' if no active session.
        """
        with self.lock:
            session = self.sessions.get(ip)
            if session is None:
                return f"0/{len(self.expected_sequence)}"
            return f"{session['progress']}/{len(self.expected_sequence)}"

import json
import os
import threading
import time
from collections import deque
from typing import Optional


class Logger:
    """
    Structured JSON logger with both disk persistence and an in-memory ring buffer.
    Thread-safe using threading.Lock.
    """

    def __init__(self, log_file: str):
        self.log_file = log_file
        self.lock = threading.Lock()
        self.recent = deque(maxlen=100)

        # Ensure directory exists
        log_dir = os.path.dirname(log_file)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)

    def log(self, event_type: str, ip: str, port: Optional[int] = None, message: str = ""):
        """
        Write a JSON line to log_file and also keep last 100 events in memory.
        Format: {"timestamp": ISO8601, "event": event_type, "ip": ip, "port": port, "message": message}
        """
        entry = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()),
            "event": event_type,
            "ip": ip,
            "port": port,
            "message": message
        }

        with self.lock:
            self.recent.append(entry)
            try:
                with open(self.log_file, "a") as f:
                    f.write(json.dumps(entry) + "\n")
            except Exception as e:
                print(f"[!] Logger failed to write to {self.log_file}: {e}")

    def get_recent(self, n: int = 50) -> list:
        """Return last n in-memory log entries."""
        with self.lock:
            return list(self.recent)[-n:]

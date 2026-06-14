import socket
import time
import json
import sys
import os


def knock(host: str, port: int):
    """Open a TCP connection to host:port and immediately close it."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
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
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(5)
        s.connect((host, service_port))
        banner = s.recv(1024).decode()
        print(f"[SERVICE] {banner.strip()}")

        # Simple interactive echo (send one line, receive echo, close)
        try:
            msg = input("[SERVICE] Type message (or Enter to quit): ")
            if msg:
                s.sendall((msg + "\n").encode())
                echo = s.recv(1024).decode()
                print(f"[SERVICE] Echo: {echo.strip()}")
        except EOFError:
            pass
        s.close()
    except Exception as e:
        print(f"[!] Service connection failed: {e}")


if __name__ == "__main__":
    # Find config.json relative to this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, "..", "config.json")
    if not os.path.exists(config_path):
        config_path = "config.json"

    with open(config_path) as f:
        config = json.load(f)

    host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    run_knock_sequence(host, config["knock_sequence"])
    time.sleep(0.5)
    connect_to_service(host, config["service_port"])

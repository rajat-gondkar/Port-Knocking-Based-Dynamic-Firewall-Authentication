import socket
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from server.firewall import FirewallManager
    from server.logger import Logger


def start_protected_service(config: dict, firewall: "FirewallManager", logger: "Logger"):
    """
    A minimal TCP service that respects firewall rules.

    - Bind a TCP socket to config["service_port"]
    - On each connection: check firewall.is_allowed(client_ip)
      - If allowed: send welcome banner "ACCESS GRANTED. Welcome, {ip}." then echo input back
      - If not allowed: send "ACCESS DENIED." and close immediately
    - Log all connection attempts
    """
    host = config.get("host", "0.0.0.0")
    port = config.get("service_port", 2222)

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, port))
        sock.listen(5)
    except OSError as e:
        print(f"[!] Failed to bind protected service to {host}:{port} — {e}")
        return

    print(f"[+] Protected service started on {host}:{port}")

    while True:
        try:
            conn, addr = sock.accept()
            client_ip = addr[0]

            if firewall.is_allowed(client_ip):
                logger.log("ACCESS_GRANTED", client_ip, port, "Connected to protected service")
                try:
                    banner = f"ACCESS GRANTED. Welcome, {client_ip}.\n"
                    conn.sendall(banner.encode())

                    # Simple echo loop
                    while True:
                        data = conn.recv(1024)
                        if not data:
                            break
                        conn.sendall(data)
                except (ConnectionResetError, BrokenPipeError):
                    pass
                finally:
                    conn.close()
            else:
                logger.log("ACCESS_DENIED", client_ip, port, "Connection rejected — not authenticated")
                try:
                    conn.sendall(b"ACCESS DENIED.\n")
                except:
                    pass
                conn.close()

        except OSError:
            break
        except Exception as e:
            print(f"[!] Error in protected service: {e}")

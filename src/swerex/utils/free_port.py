import socket
from threading import Lock


_FREE_PORT_LOCK = Lock()

def find_free_port() -> int:
    with _FREE_PORT_LOCK:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("", 0))
            return s.getsockname()[1]

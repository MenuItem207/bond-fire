from __future__ import annotations

import json
import socket
import threading
from typing import Callable, Optional


class UDPListener:
    def __init__(self, port: int, on_packet: Callable[[dict], None]) -> None:
        self._port = port
        self._on_packet = on_packet
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._sock: Optional[socket.socket] = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="udp-listener", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass
        if self._thread:
            self._thread.join(timeout=0.5)

    def _run(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock = sock
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("", self._port))

        while not self._stop_event.is_set():
            try:
                data, _addr = sock.recvfrom(65535)
            except OSError:
                break
            try:
                packet = json.loads(data.decode("utf-8"))
            except json.JSONDecodeError:
                continue
            self._on_packet(packet)

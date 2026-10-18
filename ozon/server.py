"""Локальный сервер для просмотра дашборда."""

from __future__ import annotations

import functools
import http.server
import socketserver
from pathlib import Path


def serve(directory: Path, port: int = 8765) -> None:
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(directory))
    try:
        with socketserver.TCPServer(("127.0.0.1", port), handler) as httpd:
            print(f"Дашборд: http://127.0.0.1:{port}/dashboard.html")
            print("Остановить: Ctrl+C")
            httpd.serve_forever()
    except OSError as exc:
        print(f"Не удалось запустить сервер на порту {port}: {exc}")

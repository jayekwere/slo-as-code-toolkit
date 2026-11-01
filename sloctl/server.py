"""Optional loopback HTTP facade for the offline simulator."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import httpx

from .simulator import Simulator


def server(state: Path, port: int = 8765) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def setup(self) -> None:
            super().setup()
            self.connection.settimeout(5)

        def log_message(self, format: str, *args: object) -> None:
            pass

        def do_GET(self) -> None:
            self.respond()

        def do_POST(self) -> None:
            self.respond()

        def do_PUT(self) -> None:
            self.respond()

        def respond(self) -> None:
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if size < 0 or size > 65536:
                    self.send_error(413)
                    return
                if self.headers.get("Transfer-Encoding"):
                    self.send_error(400)
                    return
                content = self.rfile.read(size)
                if len(content) != size:
                    self.send_error(400)
                    return
                sim = Simulator(state)
                try:
                    response = sim.handle(
                        httpx.Request(self.command, "http://127.0.0.1" + self.path, content=content)
                    )
                finally:
                    sim.close()
                self.send_response(response.status_code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(response.content)))
                self.end_headers()
                self.wfile.write(response.content)
            except (ValueError, OSError):
                self.send_error(400)

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)

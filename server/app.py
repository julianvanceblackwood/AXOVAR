"""Loopback-only API for AXOVAR replay and research fixtures."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import threading
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from server import audit, intelligence, portfolio, settlement

ALLOWED = ("NORMAL-001", "DEGRADED-001")
FILES = {"/": ("index.html", "text/html; charset=utf-8"),
         "/app.js": ("app.js", "text/javascript; charset=utf-8"),
         "/style.css": ("style.css", "text/css; charset=utf-8"),
         "/intelligence.js": ("intelligence.js", "text/javascript; charset=utf-8")}


@dataclass
class Session:
    scenario: str = "NORMAL-001"
    step: int = 0
    lock: threading.Lock = field(default_factory=threading.Lock)


def create_handler(root: Path, binary: Path, session: Session):
    root, binary = root.resolve(), binary.resolve()

    class Handler(BaseHTTPRequestHandler):
        server_version = "AXOVAR-Research/0.1"

        def log_message(self, fmt, *args):
            # Avoid reflecting untrusted request content to a shared log by default.
            pass

        def respond(self, status: int, data: bytes, content_type: str):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Content-Security-Policy", "default-src 'self'; connect-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; base-uri 'none'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(data)

        def output(self, payload: object, code: int = 200):
            self.respond(code, json.dumps(payload, separators=(",", ":")).encode(), "application/json; charset=utf-8")

        def error(self, code: int, message: str):
            self.output({"error": message}, code)

        def data(self, scenario: str, step: int):
            f = root / "scenarios" / (scenario + ".csv")
            # Only whitelisted scenario filenames are accepted.
            if scenario not in ALLOWED:
                raise ValueError("unknown scenario")
            result = subprocess.run([str(binary), "--scenario", str(f), str(step)],
                                    capture_output=True, text=True, timeout=5, check=True)
            try:
                return json.loads(result.stdout)
            except json.JSONDecodeError as exc:
                raise subprocess.SubprocessError("invalid engine response") from exc

        def local_host(self) -> bool:
            # A browser may reach loopback through a hostile hostname (DNS rebinding).
            # Require the actual request authority to be the known local listener.
            host = self.headers.get("Host", "")
            port = self.server.server_port
            return host in (f"127.0.0.1:{port}", f"localhost:{port}")

        def do_GET(self):
            if not self.local_host():
                self.error(403, "local host required")
                return
            path = urlsplit(self.path).path
            if path in FILES:
                filename, mimetype = FILES[path]
                self.respond(200, (root / "web" / filename).read_bytes(), mimetype)
                return
            if path == "/api/health":
                self.output({"service": "AXOVAR", "stage": "G0-G5 research", "status": "OK", "simulation_only": True})
                return
            if path == "/api/intelligence/status":
                self.output({**intelligence.status(), "examples": list(intelligence.EXAMPLES),
                             "read_only": True, "simulation_only": True})
                return
            if path == "/api/scenarios":
                self.output({"scenarios": [{"id": x, "description": "Normal market" if x == "NORMAL-001" else "Correlated degraded market evidence"} for x in ALLOWED]})
                return
            if path == "/api/risk/portfolio":
                try:
                    report = portfolio.load_fixture(root / "scenarios" / "PORTFOLIO-001.json")
                    self.output(report)
                except (OSError, ValueError, TypeError, KeyError):
                    self.error(500, "synthetic portfolio report unavailable")
                return
            if path == "/api/settlement":
                try:
                    report = settlement.load_fixture(root / "scenarios" / "SETTLEMENT-001.json")
                    self.output(report)
                except (OSError, ValueError, TypeError, KeyError):
                    self.error(500, "synthetic settlement report unavailable")
                return
            if path == "/api/state":
                with session.lock:
                    scenario, step = session.scenario, session.step
                try:
                    self.output(self.data(scenario, step))
                except (subprocess.SubprocessError, ValueError, OSError) as exc:
                    self.error(500, f"research engine failed: {type(exc).__name__}")
                return
            if path == "/api/audit/receipt":
                with session.lock:
                    scenario, step = session.scenario, session.step
                try:
                    path = root / "scenarios" / (scenario + ".csv")
                    before = path.read_bytes()
                    snapshot = self.data(scenario, step)
                    after = path.read_bytes()
                    if before != after:
                        raise ValueError("fixture changed during replay")
                    self.output(audit.build_receipt(snapshot, before))
                except (subprocess.SubprocessError, OSError, ValueError, KeyError, TypeError):
                    self.error(500, "audit receipt unavailable")
                return
            if path == "/api/raw":
                with session.lock:
                    scenario = session.scenario
                try:
                    payload = (root / "scenarios" / (scenario + ".csv")).read_bytes()
                    lines = payload.decode("utf-8").splitlines()
                except (OSError, UnicodeError):
                    self.error(500, "fixture evidence unavailable")
                    return
                self.output({"scenario": scenario, "fixture_sha256": hashlib.sha256(payload).hexdigest(),
                             "records": [{"line": i + 1, "raw": line,
                                          "sha256": hashlib.sha256((line + "\n").encode()).hexdigest()}
                                         for i, line in enumerate(lines[1:], start=1) if line]})
                return
            self.error(404, "route not found")

        def do_POST(self):
            if not self.local_host():
                self.error(403, "local host required")
                return
            path = urlsplit(self.path).path
            if path not in ("/api/replay/step", "/api/replay/reset", "/api/replay/end",
                            "/api/replay/scenario", "/api/intelligence/ask"):
                self.error(404, "route not found")
                return
            origin = self.headers.get("Origin")
            host = self.headers.get("Host", "")
            if origin and origin != f"http://{host}":
                self.error(403, "cross-origin mutations are not permitted")
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                self.error(400, "invalid content length")
                return
            if not 0 <= length <= 4096:
                self.error(413, "request body too large")
                return
            try:
                payload = json.loads(self.rfile.read(length)) if length else {}
                if not isinstance(payload, dict):
                    raise ValueError("request must be an object")
                if path == "/api/intelligence/ask":
                    if self.headers.get("Content-Type", "").split(";")[0].strip().lower() != "application/json":
                        self.error(415, "JSON content type required")
                        return
                    question = payload.get("question")
                    if not isinstance(question, str) or not 2 <= len(question.strip()) <= 1000:
                        raise ValueError("question must be between 2 and 1000 characters")
                    if type(payload.get("use_model", True)) is not bool:
                        raise ValueError("use_model must be boolean")
                    with session.lock:
                        scenario, step = session.scenario, session.step
                    snapshot = self.data(scenario, step)
                    self.output(intelligence.ask(question, snapshot, payload.get("use_model", True)))
                    return
                with session.lock:
                    scenario, step = session.scenario, session.step
                    if path == "/api/replay/scenario":
                        scenario = payload.get("scenario")
                        if scenario not in ALLOWED:
                            raise ValueError("unsupported scenario")
                        step = 0
                    elif path == "/api/replay/reset":
                        step = 0
                    else:
                        total = self.data(scenario, 0)["total"]
                        step = min(total, step + 1) if path.endswith("step") else total
                    # Compute the candidate response before updating shared replay state.
                    # A failed subprocess must not commit an unseen transition.
                    snapshot = self.data(scenario, step)
                    session.scenario, session.step = scenario, step
                self.output(snapshot)
            except (ValueError, json.JSONDecodeError) as exc:
                self.error(400, str(exc))
            except (subprocess.SubprocessError, OSError):
                self.error(500, "research engine unavailable")

    return Handler


def main():
    parser = argparse.ArgumentParser(description="Run AXOVAR locally; do not expose it to the internet")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--binary", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    binary = args.binary or root / "build" / "axovar_core"
    if not binary.is_file():
        parser.error(f"core binary does not exist: {binary}; run cmake first")
    host = "127.0.0.1"
    server = ThreadingHTTPServer((host, args.port), create_handler(root, binary, Session()))
    print(f"AXOVAR research: http://{host}:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

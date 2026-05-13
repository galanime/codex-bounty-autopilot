#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ipaddress
import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from runtime_state import STATE_PATH, read_state


ROOT = Path(__file__).resolve().parents[1]
WEB_DIR = ROOT / "web"


def is_loopback_host(host: str) -> bool:
    if host in {"localhost", "127.0.0.1", "::1"}:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


class DashboardHandler(BaseHTTPRequestHandler):
    server_version = "BountyDashboard/0.1"

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"[dashboard] {self.address_string()} - {fmt % args}")

    def send_json(self, data: object, status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/state":
            self.send_json(read_state(STATE_PATH))
            return
        if parsed.path == "/api/health":
            state = read_state(STATE_PATH)
            self.send_json({"ok": state.get("health", {}).get("ok", True), "updated_at": state.get("updated_at")})
            return

        rel = parsed.path.lstrip("/") or "index.html"
        if ".." in Path(rel).parts:
            self.send_error(403)
            return
        path = WEB_DIR / rel
        if path.is_dir():
            path = path / "index.html"
        if not path.exists():
            self.send_error(404)
            return
        content = path.read_bytes()
        ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if path.suffix in {".html", ".css", ".js"}:
            ctype += "; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_HEAD(self) -> None:
        parsed = urlparse(self.path)
        rel = parsed.path.lstrip("/") or "index.html"
        if ".." in Path(rel).parts:
            self.send_error(403)
            return
        path = WEB_DIR / rel
        if path.is_dir():
            path = path / "index.html"
        if not path.exists():
            self.send_error(404)
            return
        ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if path.suffix in {".html", ".css", ".js"}:
            ctype += "; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument(
        "--allow-public",
        action="store_true",
        help="Allow binding to a non-loopback address. This exposes local bounty state and is not recommended.",
    )
    args = parser.parse_args()

    if not args.allow_public and not is_loopback_host(args.host):
        print("Refusing to bind dashboard to a non-loopback host.")
        print("The dashboard exposes local workflow state, wallet id, PR status, and earnings estimates.")
        print("Use --host 127.0.0.1, or pass --allow-public only if you have added your own network protection.")
        return 2

    server = ThreadingHTTPServer((args.host, args.port), DashboardHandler)
    print(f"Dashboard: http://{args.host}:{args.port}")
    print(f"State: {STATE_PATH}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Stopping dashboard.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .db import init_db
from .service import get_dashboard, ingest_invoice, register_decision


ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"


class Handler(BaseHTTPRequestHandler):
    def _send(self, status=200, content_type="application/json", body=b""):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, payload, status=200):
        self._send(status, "application/json", json.dumps(payload, ensure_ascii=False).encode("utf-8"))

    def _read_json(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def do_OPTIONS(self):
        self._send(204)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            self._json({"ok": True, "service": "controle-faturas-python"})
            return
        if parsed.path == "/api/dashboard":
            invoice_id = parse_qs(parsed.query).get("invoice_id", [None])[0]
            self._json(get_dashboard(invoice_id))
            return
        if parsed.path in ("/", "/dashboard"):
            html = (PUBLIC / "index.html").read_bytes()
            self._send(200, "text/html; charset=utf-8", html)
            return
        self._json({"ok": False, "error": "Not found"}, 404)

    def do_HEAD(self):
        parsed = urlparse(self.path)
        if parsed.path in ("/", "/dashboard", "/api/health", "/api/dashboard"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        try:
            if self.path == "/api/intake":
                result = ingest_invoice(self._read_json())
                self._json({"ok": True, **result})
                return
            if self.path == "/api/decision":
                result = register_decision(self._read_json())
                self._json({"ok": True, **result})
                return
            self._json({"ok": False, "error": "Not found"}, 404)
        except Exception as exc:
            self._json({"ok": False, "error": str(exc)}, 500)


def main():
    init_db()
    host = "0.0.0.0"
    port = 8790
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Controle de faturas running on http://127.0.0.1:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()

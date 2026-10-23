"""只在 127.0.0.1 开放的实时面板、SSE 和获授权 SDK 事件入口。"""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hmac
import json
from pathlib import Path
import queue
import secrets
import sys
import threading
from urllib.parse import urlsplit

from core import normalize_sdk_batch, normalize_external_batch


def viewer_path() -> Path:
    # PyInstaller --onefile 解压后的资源目录
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)) / "viewer.html"


class LiveServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, hub, status, port=17321):
        self.hub = hub
        self.status = status
        self.token = secrets.token_urlsafe(32)
        self.closing = threading.Event()
        super().__init__(("127.0.0.1", port), Handler)

    def start(self):
        self.worker = threading.Thread(target=self.serve_forever, name="local-http", daemon=True)
        self.worker.start()

    def stop(self):
        self.closing.set()
        self.shutdown()
        self.server_close()


class Handler(BaseHTTPRequestHandler):
    server: LiveServer
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        # 直播期间不打印观众消息到控制台
        pass

    def _host_ok(self):
        return self.headers.get("Host", "").split(":")[0].lower() in {"127.0.0.1", "localhost"}

    def _reply(self, status, body: bytes, content_type="application/json; charset=utf-8"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status, value):
        self._reply(status, json.dumps(value, ensure_ascii=False).encode("utf-8"))

    def do_GET(self):
        if not self._host_ok():
            return self._json(403, {"error": "invalid host"})
        route = urlsplit(self.path).path
        if route in ("/", "/live"):
            try:
                content = viewer_path().read_bytes()
            except OSError:
                return self._json(500, {"error": "viewer missing"})
            return self._reply(200, content, "text/html; charset=utf-8")
        if route == "/api/history":
            return self._json(200, self.server.hub.snapshot())
        if route == "/api/status":
            return self._json(200, self.server.status())
        if route != "/api/stream":
            return self._json(404, {"error": "not found"})

        subscriber = self.server.hub.subscribe()
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache, no-transform")
            self.send_header("Connection", "keep-alive")
            self.send_header("X-Accel-Buffering", "no")
            self.end_headers()
            self.wfile.write(b": connected\n\n")
            self.wfile.flush()
            while not self.server.closing.is_set():
                try:
                    event = subscriber.get(timeout=10)
                    payload = json.dumps(event, ensure_ascii=False)
                    self.wfile.write(("data: " + payload + "\n\n").encode("utf-8"))
                except queue.Empty:
                    self.wfile.write(b": heartbeat\n\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            self.server.hub.unsubscribe(subscriber)
            self.close_connection = True

    def do_POST(self):
        if not self._host_ok():
            return self._json(403, {"error": "invalid host"})
        if urlsplit(self.path).path != "/api/ingest":
            return self._json(404, {"error": "not found"})
        if not hmac.compare_digest(self.headers.get("X-Local-Token", ""), self.server.token):
            return self._json(401, {"error": "invalid local token"})
        try:
            size = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return self._json(400, {"error": "invalid content length"})
        if not 0 < size <= 256 * 1024:
            return self._json(413, {"error": "invalid body size"})
        try:
            document = json.loads(self.rfile.read(size).decode("utf-8"))
            events = normalize_sdk_batch(document) or normalize_external_batch(document)
        except (ValueError, UnicodeError, TypeError, OverflowError):
            return self._json(400, {"error": "invalid payload"})
        accepted = sum(self.server.hub.publish(event) for event in events)
        self._json(200, {"accepted": accepted, "received": len(events)})

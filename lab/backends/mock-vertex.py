#!/usr/bin/env python3
"""mock-vertex: stands for Claude on Vertex AI reached through LCL's Private Service Connect.

What Kong's `gemini` provider does for a `claude-*` model, and what this mock answers:

  POST https://<api_endpoint>/token                        (gcp_oauth_token_url, JWT-bearer grant)
       -> {"access_token": ..., "expires_in": 3600, "token_type": "Bearer"}
  POST https://<api_endpoint>/v1/projects/<p>/locations/<l>/publishers/anthropic/models/<m>:rawPredict
       -> Anthropic Messages response
  POST ...:streamRawPredict
       -> Anthropic Messages SSE stream

Admin (plain HTTP, cluster-internal, port 8080):
  POST /admin/fault   {"status": 429, "count": 5}   next N model calls fail with that status
  POST /admin/fault   {"status": 0}                 clear
  GET  /admin/stats                                 counters per model and per status
  GET  /healthz

Standard library only. TLS cert/key from the mounted fleet wildcard Secret.
"""
import json
import os
import re
import ssl
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TLS_PORT = int(os.environ.get("TLS_PORT", "8443"))
ADMIN_PORT = int(os.environ.get("ADMIN_PORT", "8080"))
CERT = os.environ.get("TLS_CERT", "/tls/tls.crt")
KEY = os.environ.get("TLS_KEY", "/tls/tls.key")

MODEL_PATH = re.compile(r"/publishers/anthropic/models/([^/:]+):(rawPredict|streamRawPredict)$")

lock = threading.Lock()
fault = {"status": 0, "count": 0}
stats = {"tokens_issued": 0, "calls": {}, "statuses": {}}


def count(key, bucket):
    with lock:
        stats[bucket][key] = stats[bucket].get(key, 0) + 1


def take_fault():
    with lock:
        if fault["status"] and fault["count"] > 0:
            fault["count"] -= 1
            return fault["status"]
    return 0


def last_user_text(body):
    for msg in reversed(body.get("messages", [])):
        if msg.get("role") != "user":
            continue
        content = msg.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = [c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text"]
            if parts:
                return " ".join(parts)
    return ""


def estimate_tokens(body):
    return max(1, len(json.dumps(body.get("messages", []))) // 4)


class Handler(BaseHTTPRequestHandler):
    server_version = "mock-vertex/1.0"

    def log_message(self, fmt, *args):  # one line per request on stdout
        print("%s %s" % (self.address_string(), fmt % args), flush=True)

    def _json(self, status, obj):
        data = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _body(self):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        return raw

    # ------------------------------------------------------------------ public (TLS)
    def do_POST(self):
        raw = self._body()
        if self.server.admin:
            return self.admin_post(raw)
        if self.path.split("?")[0].endswith("/token"):
            with lock:
                stats["tokens_issued"] += 1
            return self._json(200, {"access_token": "mock-" + uuid.uuid4().hex,
                                    "expires_in": 3600, "token_type": "Bearer"})
        m = MODEL_PATH.search(self.path.split("?")[0])
        if not m:
            return self._json(404, {"error": {"code": 404, "message": "unknown path " + self.path}})
        if not (self.headers.get("Authorization") or "").startswith("Bearer "):
            count("401", "statuses")
            return self._json(401, {"error": {"code": 401, "message": "missing OAuth bearer token"}})
        model, op = m.group(1), m.group(2)
        count(model, "calls")
        injected = take_fault()
        if injected:
            count(str(injected), "statuses")
            kind = "rate_limit_error" if injected == 429 else "api_error"
            return self._json(injected, {"type": "error", "error": {"type": kind,
                              "message": "mock-vertex injected %d" % injected}})
        try:
            body = json.loads(raw or b"{}")
        except ValueError:
            return self._json(400, {"type": "error", "error": {"type": "invalid_request_error",
                              "message": "body is not JSON"}})
        text = "[mock-vertex %s] %s" % (model, (last_user_text(body) or "hello")[:200])
        in_tok, out_tok = estimate_tokens(body), max(1, len(text) // 4)
        count("200", "statuses")
        if op == "streamRawPredict" or body.get("stream"):
            return self.stream(model, text, in_tok, out_tok)
        return self._json(200, {
            "id": "msg_" + uuid.uuid4().hex[:24], "type": "message", "role": "assistant",
            "model": model, "content": [{"type": "text", "text": text}],
            "stop_reason": "end_turn", "stop_sequence": None,
            "usage": {"input_tokens": in_tok, "output_tokens": out_tok},
        })

    def stream(self, model, text, in_tok, out_tok):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()

        def event(name, obj):
            self.wfile.write(("event: %s\ndata: %s\n\n" % (name, json.dumps(obj))).encode())
            self.wfile.flush()

        event("message_start", {"type": "message_start", "message": {
            "id": "msg_" + uuid.uuid4().hex[:24], "type": "message", "role": "assistant", "model": model,
            "content": [], "stop_reason": None, "stop_sequence": None,
            "usage": {"input_tokens": in_tok, "output_tokens": 1}}})
        event("content_block_start", {"type": "content_block_start", "index": 0,
                                      "content_block": {"type": "text", "text": ""}})
        for i in range(0, len(text), 24):
            event("content_block_delta", {"type": "content_block_delta", "index": 0,
                                          "delta": {"type": "text_delta", "text": text[i:i + 24]}})
            time.sleep(0.02)
        event("content_block_stop", {"type": "content_block_stop", "index": 0})
        event("message_delta", {"type": "message_delta",
                                "delta": {"stop_reason": "end_turn", "stop_sequence": None},
                                "usage": {"output_tokens": out_tok}})
        event("message_stop", {"type": "message_stop"})

    # ------------------------------------------------------------------ admin (plain HTTP)
    def admin_post(self, raw):
        if self.path != "/admin/fault":
            return self._json(404, {"error": "unknown admin path"})
        req = json.loads(raw or b"{}")
        with lock:
            fault["status"] = int(req.get("status", 0))
            fault["count"] = int(req.get("count", 1_000_000 if fault["status"] else 0))
            current = dict(fault)
        return self._json(200, {"fault": current})

    def do_GET(self):
        if self.path == "/healthz":
            return self._json(200, {"ok": True})
        if self.server.admin and self.path == "/admin/stats":
            with lock:
                return self._json(200, {"fault": dict(fault), **json.loads(json.dumps(stats))})
        return self._json(404, {"error": "not found"})


def serve(port, admin):
    httpd = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    httpd.admin = admin
    if not admin:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(CERT, KEY)
        httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)
    print("mock-vertex listening on :%d (%s)" % (port, "admin/http" if admin else "tls"), flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    threading.Thread(target=serve, args=(ADMIN_PORT, True), daemon=True).start()
    serve(TLS_PORT, False)

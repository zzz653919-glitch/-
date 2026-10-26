"""Lokal soxta Anthropic Messages API (SSE oqim formati). Haqiqiy SDK shu serverga ulanadi: tarmoq kodi, oqim, xato xaritalash sinaladi."""
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def sse(event: str, data: dict) -> bytes:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n".encode()


def message_events(chunks, stop_reason="end_turn", model="claude-opus-5-5", delay_first=0.0, gap=0.0):
    yield sse("message_start", {"type": "message_start", "message": {"id": "msg_1", "type": "message", "role": "assistant", "model": model, "content": [],
              "stop_reason": None, "stop_sequence": None, "usage": {"input_tokens": 12, "output_tokens": 1}}})
    if chunks:
        yield sse("content_block_start", {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}})
        for i, c in enumerate(chunks):
            if i == 0 and delay_first:
                time.sleep(delay_first)
            elif gap:
                time.sleep(gap)
            yield sse("content_block_delta", {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": c}})
        yield sse("content_block_stop", {"type": "content_block_stop", "index": 0})
    yield sse("message_delta", {"type": "message_delta", "delta": {"stop_reason": stop_reason, "stop_sequence": None}, "usage": {"output_tokens": 20}})
    yield sse("message_stop", {"type": "message_stop"})


class MockAnthropic:
    """Navbat bilan «ssenariylar» beradi: har bir ssenariy — ('stream', kwargs) yoki ('error', status, type, message, headers) yoki ('hang', sekund)."""

    def __init__(self):
        self.requests: list[dict] = []
        self.script: list[tuple] = []
        self.default = ("stream", {"chunks": ["Salom! ", "Yaxshiman, ", "rahmat."]})
        self._lock = threading.Lock()
        outer = self

        class H(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *a):
                pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers.get("content-length", 0))) or b"{}")
                with outer._lock:
                    outer.requests.append({"path": self.path, "headers": {k.lower(): v for k, v in self.headers.items()}, "body": body})
                    step = outer.script.pop(0) if outer.script else outer.default
                if step[0] == "error":
                    _, status, etype, msg, headers = (list(step) + [{}])[:5]
                    data = json.dumps({"type": "error", "error": {"type": etype, "message": msg}}).encode()
                    self.send_response(status)
                    self.send_header("content-type", "application/json"); self.send_header("content-length", str(len(data)))
                    for k, v in (headers or {}).items():
                        self.send_header(k, v)
                    self.end_headers(); self.wfile.write(data)
                    return
                if step[0] == "hang":
                    time.sleep(step[1])
                    return
                self.send_response(200)
                self.send_header("content-type", "text/event-stream"); self.send_header("cache-control", "no-cache"); self.send_header("transfer-encoding", "chunked")
                self.end_headers()
                try:
                    for ev in message_events(**step[1]):
                        self.wfile.write(f"{len(ev):x}\r\n".encode() + ev + b"\r\n"); self.wfile.flush()
                    self.wfile.write(b"0\r\n\r\n"); self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    pass

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.httpd.daemon_threads = True
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        self._t = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self._t.start()

    def close(self):
        self.httpd.shutdown(); self.httpd.server_close()

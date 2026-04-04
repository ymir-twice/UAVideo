import json
from http.server import BaseHTTPRequestHandler, HTTPServer


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if not self.path.endswith("/chat/completions"):
            self.send_response(404)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8")
        payload = json.loads(body) if body else {}
        msgs = payload.get("messages") or []
        user = ""
        for m in reversed(msgs):
            if m.get("role") == "user" and isinstance(m.get("content"), str):
                user = m["content"]
                break
        out = {
            "id": "stub",
            "object": "chat.completion",
            "created": 0,
            "model": payload.get("model") or "stub",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": user[:4000]}, "finish_reason": "stop"}],
        }
        data = json.dumps(out).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main():
    HTTPServer(("0.0.0.0", 18081), Handler).serve_forever()


if __name__ == "__main__":
    main()


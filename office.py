"""2D 오피스 화면 서버.

python office.py  →  http://localhost:8565 이 열리고, '지금 점검' 버튼을 누르면
부서들이 실제로 일하는 순서대로 캐릭터가 움직인다 (Server-Sent Events로 실시간 전달).
"""
import json
import queue
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from dotenv import load_dotenv

from scout.events import EventBus
from scout.pipeline import DATA, execute

ROOT = Path(__file__).parent
PORT = 8565
RUN_LOCK = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # 터미널에 요청 로그를 찍지 않음
        pass

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        url = urlparse(self.path)
        if url.path == "/":
            self._send(200, (ROOT / "static" / "office.html").read_bytes(), "text/html; charset=utf-8")
        elif url.path == "/replay":
            path = DATA / "events" / "latest.json"
            body = path.read_bytes() if path.exists() else b"[]"
            self._send(200, body, "application/json; charset=utf-8")
        elif url.path == "/run":
            self._stream_run(send=parse_qs(url.query).get("send") == ["1"])
        else:
            self._send(404, b"not found", "text/plain")

    def _stream_run(self, send: bool) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()

        def push(ev: dict) -> None:
            self.wfile.write(f"data: {json.dumps(ev, ensure_ascii=False)}\n\n".encode("utf-8"))
            self.wfile.flush()

        if not RUN_LOCK.acquire(blocking=False):
            push({"dept": "consultant", "status": "busy", "msg": "이미 점검이 진행 중이에요"})
            return
        events: queue.Queue = queue.Queue()
        bus = EventBus(delay=0.6)  # 화면에서 흐름이 보이도록 이벤트 사이를 조금 띄움
        bus.subscribe(events.put)

        def work():
            try:
                execute(bus, send=send)
            except Exception as e:  # 화면에 실패를 알리고 끝냄
                events.put({"dept": "consultant", "status": "error", "msg": f"실행 실패: {e}"})
            finally:
                events.put(None)

        threading.Thread(target=work, daemon=True).start()
        try:
            while (ev := events.get()) is not None:
                push(ev)
            push({"dept": "consultant", "status": "end", "msg": "끝"})
        except (BrokenPipeError, ConnectionResetError):
            pass  # 사용자가 창을 닫음 — 점검 자체는 끝까지 진행
        finally:
            RUN_LOCK.release()


if __name__ == "__main__":
    load_dotenv(ROOT / ".env")
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"2D 오피스: http://localhost:{PORT}  (종료: Ctrl+C)")
    if "--no-browser" not in sys.argv:
        threading.Timer(0.5, lambda: webbrowser.open(f"http://localhost:{PORT}")).start()
    server.serve_forever()

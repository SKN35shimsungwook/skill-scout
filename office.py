"""skill-scout 화면 서버 (상담 채팅 + 2D 사무실).

python office.py  →  http://localhost:8565
- 상담: 새 작업을 물어보면 상담팀이 받아 부서들이 준비물(스킬·플러그인)을 챙겨 준다
- 사무실: 아침 점검을 실행하거나 지난 실행을 다시 본다
부서들의 진행 상황은 Server-Sent Events로 실시간 전달한다.
"""
import json
import os
import queue
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from dotenv import load_dotenv

from scout.events import EventBus
from scout.graph_chat import run_chat
from scout.installed import installed_tools
from scout.pipeline import DATA, execute

ROOT = Path(__file__).parent
STATIC = ROOT / "static"
PORT = 8565
RUN_LOCK = threading.Lock()  # 아침 점검은 한 번에 하나만
TYPES = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8", ".js": "text/javascript; charset=utf-8"}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # 터미널에 요청 로그를 찍지 않음
        pass

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, data) -> None:
        self._send(200, json.dumps(data, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def do_GET(self):
        url = urlparse(self.path)
        qs = parse_qs(url.query)
        if url.path == "/":
            self._send(200, (STATIC / "app.html").read_bytes(), TYPES[".html"])
        elif url.path.startswith("/static/"):
            path = (STATIC / url.path.removeprefix("/static/")).resolve()
            if path.parent == STATIC.resolve() and path.suffix in TYPES and path.exists():
                self._send(200, path.read_bytes(), TYPES[path.suffix])
            else:
                self._send(404, b"not found", "text/plain")
        elif url.path == "/replay":
            path = DATA / "events" / "latest.json"
            self._send(200, path.read_bytes() if path.exists() else b"[]", "application/json; charset=utf-8")
        elif url.path == "/api/installed":
            self._json(installed_tools())
        elif url.path == "/api/status":  # 설정 상태만 알려 준다 (키 값은 보내지 않음)
            self._json({"gemini": bool(os.getenv("GEMINI_API_KEY")), "model": os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
                        "discord": bool(os.getenv("DISCORD_WEBHOOK_URL"))})
        elif url.path == "/run":
            send = qs.get("send") == ["1"]
            self._stream(lambda bus: execute(bus, send=send), delay=0.6, lock=RUN_LOCK)
        elif url.path == "/chat":
            question = (qs.get("q") or [""])[0].strip()[:500]
            if not question:
                self._send(400, "질문이 비어 있어요".encode("utf-8"), "text/plain; charset=utf-8")
            else:
                self._stream(lambda bus: run_chat(bus, DATA, question), delay=0.35)
        else:
            self._send(404, b"not found", "text/plain")

    def _stream(self, job, delay: float, lock: threading.Lock | None = None) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()

        def push(ev: dict) -> None:
            self.wfile.write(f"data: {json.dumps(ev, ensure_ascii=False)}\n\n".encode("utf-8"))
            self.wfile.flush()

        if lock and not lock.acquire(blocking=False):
            push({"dept": "consultant", "status": "busy", "msg": "이미 점검이 진행 중이에요"})
            return
        events: queue.Queue = queue.Queue()
        bus = EventBus(delay=delay)  # 화면에서 흐름이 보이도록 이벤트 사이를 조금 띄움
        bus.subscribe(events.put)

        def work():
            try:
                job(bus)
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
            pass  # 사용자가 창을 닫음 — 작업 자체는 끝까지 진행
        finally:
            if lock:
                lock.release()


if __name__ == "__main__":
    load_dotenv(ROOT / ".env")
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"skill-scout: http://localhost:{PORT}  (종료: Ctrl+C)")
    if "--no-browser" not in sys.argv:
        threading.Timer(0.5, lambda: webbrowser.open(f"http://localhost:{PORT}")).start()
    server.serve_forever()

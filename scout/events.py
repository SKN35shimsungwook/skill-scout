"""부서(에이전트)들이 지금 무엇을 하는지 기록하는 이벤트 버스.

2D 오피스 화면은 이 이벤트를 실시간으로 받아 캐릭터를 움직인다.
실행이 끝나면 data/events/에 저장해서 '지난 실행 다시 보기'에 쓴다.
"""
import json
import threading
import time
from pathlib import Path

DEPTS = {
    "collector": "수집기",
    "inspector": "점검팀",
    "verifier": "검증팀",
    "briefer": "브리핑팀",
    "consultant": "상담팀",
}


class EventBus:
    def __init__(self, delay: float = 0.0):
        self.history: list[dict] = []
        self._subscribers: list = []
        self._lock = threading.Lock()
        self.delay = delay  # 화면에서 흐름이 보이도록 이벤트 사이에 잠깐 쉬는 시간(초). 아침 자동 실행은 0
        self._t0 = time.time()

    def subscribe(self, fn) -> None:
        self._subscribers.append(fn)

    def emit(self, dept: str, status: str, msg: str, data=None) -> None:
        """status: start(일 시작) · work(진행 중) · done(완료) · handoff(다음 부서로 전달) · retry(재검토 요청) · result(최종 결과)"""
        ev = {"t": round(time.time() - self._t0, 2), "dept": dept, "name": DEPTS.get(dept, dept),
              "status": status, "msg": msg, "data": data}
        with self._lock:
            self.history.append(ev)
        for fn in self._subscribers:
            fn(ev)
        if self.delay and status in ("start", "work", "done", "handoff", "retry"):
            time.sleep(self.delay)

    def save(self, folder: Path) -> Path:
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{time.strftime('%Y%m%d-%H%M%S')}.json"
        payload = json.dumps(self.history, ensure_ascii=False, indent=1)
        path.write_text(payload, encoding="utf-8")
        (folder / "latest.json").write_text(payload, encoding="utf-8")
        return path

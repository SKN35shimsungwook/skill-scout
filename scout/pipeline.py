"""한 번의 아침 점검 실행 (아침 자동 실행과 2D 오피스 화면이 함께 쓴다).

디스코드에는 섹션마다 메시지를 따로 보낸다:
어제 작업 → 할일 지킴이 → 상태 점검 → 사용량·팁·업데이트 → 도구 추천 → (그 주 첫 전송) 지난주 요약
"""
import json
import os
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from . import briefing
from .events import EventBus
from .graph import run_graph
from .morning import build_sections, week_start, weekly_due

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
STATE = DATA / "state.json"
EARLIEST_HOUR = 6  # 자동 실행은 이 시각 전에는 보내지 않는다 (밤샘 작업 중 잠금 해제 대비)


def _load_state() -> dict:
    return json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {"seen": [], "recommended": {}}


def scheduled_skip_reason(state: dict, now: datetime) -> str | None:
    """자동 실행(08:00·잠금 해제·로그인)을 건너뛸 이유. 보내도 되면 None."""
    if now.hour < EARLIEST_HOUR:
        return f"{EARLIEST_HOUR}시 전이라 건너뜀"
    if state.get("last_sent_date") == now.date().isoformat():
        return "오늘 이미 보내서 건너뜀"
    return None


def should_skip_scheduled() -> str | None:
    return scheduled_skip_reason(_load_state(), datetime.now())


TODO_SCRIPT = Path.home() / ".claude" / "skills" / "todo-keeper" / "scripts" / "todo.py"


def todo_section(bus: EventBus) -> str:
    """할일 지킴이(todo-keeper) 요약. 스크립트가 없거나 실패해도 브리핑은 그대로 보낸다."""
    if not TODO_SCRIPT.exists():
        return ""
    try:
        r = subprocess.run([sys.executable, "-I", "-X", "utf8", str(TODO_SCRIPT), "brief"],
                           capture_output=True, text=True, encoding="utf-8", timeout=30)
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception as e:  # noqa: BLE001
        bus.emit("briefer", "todo_error", f"할일 요약 실패: {e}")
        return ""


def execute(bus: EventBus, send: bool, days: int = 30, top: int = 5, weekly: bool | None = None) -> dict:
    DATA.mkdir(exist_ok=True)
    state = _load_state()
    week_ago = (datetime.now() - timedelta(days=7)).isoformat()
    recent = {k: v for k, v in state["recommended"].items() if v >= week_ago}

    today = date.today()
    include_weekly = weekly_due(state, today) if weekly is None else weekly
    extra = build_sections(DATA, state, bus, include_weekly)
    out = run_graph(bus, DATA, days, top, recent, state["seen"])
    sections = extra[:3] + [out["text"]] + extra[3:]  # 주간 요약은 맨 뒤
    todo = todo_section(bus)
    if todo:
        sections.insert(1 if sections else 0, todo)  # 어제 작업 바로 다음
    text = "\n\n━━━━━━━━━━\n\n".join(sections)
    (DATA / "latest_briefing.md").write_text(text, encoding="utf-8")
    (DATA / "latest_ranking.json").write_text(json.dumps(out["ranked"][:50], ensure_ascii=False, indent=1), encoding="utf-8")

    sent, error = False, None
    if send:
        url = os.getenv("DISCORD_WEBHOOK_URL")
        if not url:
            error = "DISCORD_WEBHOOK_URL이 .env에 없어서 전송하지 않았어요."
        else:
            briefing.send_discord(url, sections)
            sent = True
            now = datetime.now()
            state["recommended"].update({p["id"]: now.isoformat() for p in out["picks"] + out["new_hits"]})
            state["last_sent_date"] = now.date().isoformat()
            if include_weekly:
                state["weekly_sent"] = week_start(now.date()).isoformat()
    bus.emit("briefer", "sent" if sent else "not_sent",
             f"디스코드에 메시지 {len(sections)}개 전송 완료" if sent else (error or "전송 안 함 (미리보기)"))

    pending = state.pop("claude_code_release_pending", None)
    if sent and pending:
        state["claude_code_release"] = pending
    state["seen"] = sorted(set(state["seen"]) | {it["id"] for it in out["items"]})
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    bus.save(DATA / "events")
    return {"text": text, "sent": sent, "error": error}

"""한 번의 점검 실행 (아침 자동 실행과 2D 오피스 화면이 함께 쓴다)."""
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

from . import briefing
from .events import EventBus
from .graph import run_graph

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
STATE = DATA / "state.json"


def _load_state() -> dict:
    return json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {"seen": [], "recommended": {}}


def execute(bus: EventBus, send: bool, days: int = 30, top: int = 5) -> dict:
    DATA.mkdir(exist_ok=True)
    state = _load_state()
    week_ago = (datetime.now() - timedelta(days=7)).isoformat()
    recent = {k: v for k, v in state["recommended"].items() if v >= week_ago}

    out = run_graph(bus, DATA, days, top, recent, state["seen"])
    text = out["text"]
    (DATA / "latest_briefing.md").write_text(text, encoding="utf-8")
    (DATA / "latest_ranking.json").write_text(json.dumps(out["ranked"][:50], ensure_ascii=False, indent=1), encoding="utf-8")

    sent, error = False, None
    if send:
        url = os.getenv("DISCORD_WEBHOOK_URL")
        if not url:
            error = "DISCORD_WEBHOOK_URL이 .env에 없어서 전송하지 않았어요."
        else:
            briefing.send_discord(url, text)
            sent = True
            now = datetime.now().isoformat()
            state["recommended"].update({p["id"]: now for p in out["picks"] + out["new_hits"]})
    bus.emit("briefer", "sent" if sent else "not_sent", "디스코드 전송 완료" if sent else (error or "전송 안 함 (미리보기)"))

    state["seen"] = sorted(set(state["seen"]) | {it["id"] for it in out["items"]})
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    bus.save(DATA / "events")
    return {"text": text, "sent": sent, "error": error}

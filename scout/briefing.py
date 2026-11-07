"""아침 브리핑 문장을 만들고 디스코드로 보낸다 (LLM을 쓰지 않아 토큰 비용 0)."""
from datetime import datetime

import requests

from .signals import SIGNALS

DISCORD_LIMIT = 1900  # 디스코드 메시지 한도 2,000자보다 조금 여유


def _short(text: str, n: int = 110) -> str:
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 1] + "…"


def build(profile: dict, picks: list[dict], new_hits: list[dict], new_total: int, errors: list[str]) -> str:
    top = " · ".join(f"{SIGNALS[k][0]} {v}" for k, v in list(profile["signals"].items())[:5])
    lines = [
        f"**🧩 아침 스킬·플러그인 브리핑** ({datetime.now():%m/%d})",
        f"최근 {profile['days']}일 대화 {profile['messages']}개 기준 자주 한 일: {top}",
        "",
        "**오늘의 추천**",
    ]
    for i, p in enumerate(picks, 1):
        badge = "공식 " if p.get("official") else ""
        check = {"PASS": "✅", "WARNING": "⚠️"}.get(p.get("verdict"), "")
        lines += [
            f"{i}. **{p['name']}** ({badge}{p['kind']})  {_short(p['description'])}",
            f"   ↳ 이유: {p['reason']}",
            *([f"   ↳ 검증: {check} {p['verdict_note']}"] if p.get("verdict_note") else []),
            f"   ↳ 설치: `{p['install']}`",
        ]
    if new_hits:
        lines += ["", f"**새로 나온 것 중 내 작업 관련** (새 항목 {new_total}개 중)"]
        lines += [f"• **{p['name']}** ({p['kind']}) {_short(p['description'], 80)}  ↳ {p['reason']}" for p in new_hits]
    elif new_total:
        lines += ["", f"새로 나온 항목 {new_total}개 — 내 작업과 겹치는 건 없음"]
    if errors:
        lines += ["", "⚠️ 수집 실패: " + " / ".join(errors)]
    return "\n".join(lines)


def _chunks(text: str) -> list[str]:
    out, cur = [], ""
    for line in text.split("\n"):
        if len(cur) + len(line) + 1 > DISCORD_LIMIT:
            out.append(cur)
            cur = ""
        cur += line + "\n"
    return out + [cur] if cur.strip() else out


def send_discord(webhook_url: str, text: str) -> None:
    for chunk in _chunks(text):
        res = requests.post(webhook_url, json={"content": chunk, "allowed_mentions": {"parse": []}}, timeout=30)
        res.raise_for_status()

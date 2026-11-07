"""내 Claude Code 대화 기록에서 '자주 하는 작업'을 뽑는다.

기록 원문은 이 PC 밖으로 나가지 않는다. 결과는 신호별 횟수(숫자)뿐이다.
"""
import json
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .signals import SIGNALS, VENDORS

PROJECTS_DIR = Path.home() / ".claude" / "projects"


def _user_texts(path: Path, since: datetime):
    """한 세션 파일에서 내가 직접 쓴 메시지만 꺼낸다 (도구 결과·자동 알림은 제외)."""
    with path.open(encoding="utf-8", errors="ignore") as f:
        for line in f:
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if d.get("type") != "user" or d.get("isMeta"):
                continue
            ts = d.get("timestamp")
            if ts and datetime.fromisoformat(ts.replace("Z", "+00:00")) < since:
                continue
            content = (d.get("message") or {}).get("content")
            if isinstance(content, list):
                content = " ".join(c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text")
            if not isinstance(content, str) or not content.strip():
                continue
            if content.lstrip().startswith(("<system-reminder", "<command-", "<local-command", "<task-notification")):
                continue
            yield content[:3000]


def _count(text: str, words: list[str]) -> int:
    text = text.lower()
    n = 0
    for w in words:
        if re.fullmatch(r"[a-z0-9 .+-]+", w):  # 영어 단어는 단어 경계로 (예: 'db'가 'dbt'에 걸리지 않게)
            n += len(re.findall(rf"(?<![a-z0-9]){re.escape(w)}(?![a-z0-9])", text))
        else:
            n += text.count(w)
    return n


def build_profile(days: int = 30) -> dict:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    counts: Counter = Counter()
    vendors: set[str] = set()
    messages = sessions = 0
    for path in PROJECTS_DIR.glob("*/*.jsonl"):
        if datetime.fromtimestamp(path.stat().st_mtime, timezone.utc) < since:
            continue
        used = False
        for text in _user_texts(path, since):
            messages += 1
            used = True
            vendors |= {v for v in VENDORS if _count(text, [v])}
            for key, (_, ko_words, _) in SIGNALS.items():
                if _count(text, ko_words):
                    counts[key] += 1  # 메시지 하나당 신호 1회로 센다 (같은 말 반복에 휘둘리지 않게)
        sessions += used
    return {"days": days, "sessions": sessions, "messages": messages, "signals": dict(counts.most_common()),
            "vendors": sorted(vendors)}

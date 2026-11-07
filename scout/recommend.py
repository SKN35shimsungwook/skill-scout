"""후보마다 '내 작업과 얼마나 겹치는지' 점수를 매기고 추천 이유를 붙인다."""
import math
import re

from .profile import _count
from .signals import SIGNALS


def _matched_signals(item: dict) -> list[str]:
    text = f"{item['name']} {item['description']} {item['category']}".lower().replace("-", " ")
    return [key for key, (_, _, en_words) in SIGNALS.items() if _count(text, en_words)]


def score_items(items: list[dict], profile: dict, installed: set[str], recent: dict[str, str]) -> list[dict]:
    signals = profile["signals"]
    matched = {it["id"]: _matched_signals(it) for it in items}
    # 여러 후보에 두루 걸리는 신호(흔한 신호)는 변별력이 낮으니 가중치를 낮춘다 (IDF)
    n = len(items) or 1
    df = {k: sum(k in m for m in matched.values()) for k in SIGNALS}
    idf = {k: math.log((n + 1) / (df[k] + 1)) for k in SIGNALS}
    scored = []
    for item in items:
        if item["name"].lower() in installed or not item["description"]:
            continue
        keys = [k for k in matched[item["id"]] if signals.get(k)]
        if not keys:
            continue
        # 내가 자주 한 일 × 그 신호의 변별력. 설명이 길어 신호가 많이 걸린 후보가 유리하지 않게 상위 2개만 합산
        parts = sorted((math.log1p(signals[k]) * idf[k] for k in keys), reverse=True)
        score = sum(parts[:2])
        if item.get("official"):
            score *= 1.15
        if item.get("rank"):  # skills.sh 인기 순위 가산점
            score *= 1 + 0.3 / math.sqrt(item["rank"])
        if item["id"] in recent:  # 최근 7일 안에 이미 추천한 건 뒤로
            score *= 0.3
        keys.sort(key=lambda k: -signals[k])
        reason = " · ".join(f"{SIGNALS[k][0]} {signals[k]}회" for k in keys[:3])
        scored.append({**item, "score": round(score, 3), "signals": keys, "reason": reason})
    scored.sort(key=lambda x: -x["score"])
    return _dedupe(scored)


def _dedupe(items: list[dict]) -> list[dict]:
    """같은 이름(예: pdf 스킬이 여러 출처에 있음)은 점수가 높은 하나만 남긴다."""
    seen, out = set(), []
    for it in items:
        key = re.sub(r"[^a-z0-9]", "", it["name"].lower())
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out

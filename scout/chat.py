"""상담팀의 말하기·알아듣기 담당.

Gemini 무료 API(GEMINI_API_KEY)가 있으면 질문 이해와 답변 문장에 쓰고,
키가 없거나 한도 초과·오류가 나면 단어 매칭과 정해진 문장으로 대신한다.
Gemini에는 사용자가 채팅창에 쓴 질문과 추천 결과만 보낸다 (대화 기록·키는 보내지 않음).
"""
import json
import os
import re

import requests

from .profile import _count
from .signals import SIGNALS

API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def _model() -> str:
    return os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


def gemini(prompt: str, as_json: bool = False) -> str | None:
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        return None
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.3, **({"responseMimeType": "application/json"} if as_json else {})}}
    try:
        r = requests.post(API.format(model=_model()), headers={"x-goog-api-key": key}, json=body, timeout=25)
        r.raise_for_status()
        return r.json()["candidates"][0]["content"]["parts"][0]["text"]
    except (requests.RequestException, KeyError, IndexError, ValueError):
        return None  # 한도 초과(429)·키 오류 등은 단어 매칭으로 넘어감


GENERIC = {"frontend", "data", "docs", "review", "llm", "python", "git"}  # 여러 작업에 두루 나오는 신호


def _keyword_signals(question: str) -> list[str]:
    q = question.lower()
    hits = {k: _count(q, ko) + _count(q, en) for k, (_, ko, en) in SIGNALS.items()}
    # 같은 횟수면 구체적인 작업(예: 크롤링)을 일반적인 작업(예: 웹 화면)보다 앞에 둔다
    return [k for k, v in sorted(hits.items(), key=lambda x: (-x[1], x[0] in GENERIC)) if v][:3]


def understand(question: str) -> dict:
    """질문에서 '하려는 작업'을 뽑는다. → {task, signals, engine}"""
    menu = "\n".join(f"- {k}: {label}" for k, (label, _, _) in SIGNALS.items())
    prompt = (
        "사용자가 Claude Code로 새 작업을 하려고 한다. 질문을 읽고 아래 작업 종류 중 관련 있는 것을 "
        "중요한 순서로 최대 3개 고르고, 하려는 작업을 한국어 15자 안으로 요약해.\n"
        f"작업 종류:\n{menu}\n\n질문: {question}\n\n"
        'JSON만 출력: {"task": "...", "signals": ["key", ...]}'
    )
    text = gemini(prompt, as_json=True)
    if text:
        try:
            data = json.loads(text)
            sig = [s for s in data.get("signals", []) if s in SIGNALS][:3]
            if sig:
                return {"task": str(data.get("task", ""))[:30] or SIGNALS[sig[0]][0], "signals": sig, "engine": "Gemini"}
        except (json.JSONDecodeError, AttributeError):
            pass
    sig = _keyword_signals(question)
    task = " · ".join(SIGNALS[k][0] for k in sig) if sig else ""
    return {"task": task, "signals": sig, "engine": "단어 매칭"}


def compose(question: str, task: str, have: list[dict], install: list[dict], optional: list[dict], engine: str) -> str:
    """준비물 체크리스트를 한두 문단으로 설명한다."""
    if not (have or install or optional):
        return ("어떤 작업인지 잘 못 알아들었어요. 예를 들어 '발표자료 만들 거야', "
                "'웹사이트 크롤링 하려고 해'처럼 하려는 일을 알려 주세요.")
    if engine == "Gemini":
        listing = json.dumps({
            "이미_있음": [{"name": t["name"], "what": t["guide"]["summary"]} for t in have],
            "설치_추천": [{"name": t["name"], "what": t["guide"]["summary"]} for t in install],
            "선택": [{"name": t["name"], "what": t["guide"]["summary"], "note": t.get("verdict_note", "")} for t in optional],
        }, ensure_ascii=False)
        prompt = (
            "너는 skill-scout 회사의 상담팀이다. 사용자가 새 작업을 앞두고 준비물(스킬·플러그인)을 물었다.\n"
            f"질문: {question}\n하려는 작업: {task}\n준비물 목록(JSON): {listing}\n\n"
            "목록에 있는 이름만 써서, 무엇부터 쓰면 좋은지 한국어 존댓말 3~4문장으로 친근하게 설명해. "
            "이미 있는 건 '바로 쓰면 된다'고, 설치 추천은 왜 필요한지 한 마디씩. 목록에 없는 도구는 지어내지 마. 마크다운 쓰지 마."
        )
        text = gemini(prompt)
        if text:
            return re.sub(r"[*#`]", "", text).strip()
    parts = [f"'{task}' 작업이네요." if task else "말씀하신 작업 기준으로 정리했어요."]
    if have:
        parts.append(f"{', '.join(t['name'] for t in have)}은(는) 이미 있으니 바로 쓰시면 돼요.")
    if install:
        parts.append(f"{', '.join(t['name'] for t in install)}을(를) 설치하면 더 편해져요.")
    if optional:
        parts.append(f"필요하면 {', '.join(t['name'] for t in optional)}도 살펴보세요.")
    return " ".join(parts)

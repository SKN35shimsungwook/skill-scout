"""채팅 상담 흐름 (LangGraph) — 새 작업을 앞두고 '준비물'을 챙겨 준다.

상담팀(접수) → 수집기 → 점검팀 → 검증팀 ─(통과 부족)→ 점검팀 재검토
                                        └(충분)→ 상담팀(답변)
아침 점검과 같은 부서·같은 검사를 쓰고, 기준만 '내 사용 이력' 대신 '지금 하려는 작업'이다.
상담팀만 Gemini를 쓰고(없으면 단어 매칭), 나머지 부서는 규칙 기반이다.
"""
from pathlib import Path
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from . import catalog
from .chat import compose, understand
from .events import EventBus
from .graph import BATCH, enough_passed, verify_batch
from .guides import guide_for
from .installed import installed_tools
from .recommend import score_items
from .signals import SIGNALS, VENDORS
from .verify import RepoChecker

CHAT_TOP = 3
WEIGHTS = (10, 6, 4)  # 질문에서 뽑은 작업의 중요도 (첫 번째가 가장 중요)
FIELDS = ("name", "kind", "official", "description", "reason", "install", "url", "verdict", "verdict_note",
          "guide", "where")


class ChatState(TypedDict, total=False):
    question: str
    task: str
    signals: list
    engine: str
    items: list
    tools: list
    ranked: list
    have: list
    round: int
    candidates: list
    passed: list
    warned: list
    rejected: list
    answer: str


def build_chat_graph(bus: EventBus, data_dir: Path):
    checker = RepoChecker(data_dir / "github_cache.json")

    def intake(s: ChatState) -> dict:
        q = s["question"]
        bus.emit("consultant", "start", f"질문 접수: {q[:40]}")
        u = understand(q)
        if u["signals"]:
            bus.emit("consultant", "work", f"할 작업: {u['task']} ({u['engine']})", {"signals": u["signals"]})
            bus.emit("consultant", "handoff", "수집기에 준비물 후보 요청")
        else:
            bus.emit("consultant", "work", "어떤 작업인지 파악하지 못했어요")
        return u

    def collector(s: ChatState) -> dict:
        bus.emit("collector", "start", "준비물 후보 목록 꺼내는 중")
        items, errors = catalog.collect(data_dir, max_age=3600)
        for e in errors:
            bus.emit("collector", "work", f"⚠️ {e}")
        tools = installed_tools()
        bus.emit("collector", "done", f"후보 {len(items)}개 + 내 도구 {len(tools)}개")
        bus.emit("collector", "handoff", "점검팀에 전달")
        return {"items": items, "tools": tools}

    def inspector(s: ChatState) -> dict:
        rnd = s.get("round", 0)
        if rnd == 0:
            bus.emit("inspector", "start", f"'{s['task']}'에 필요한 도구 찾는 중")
            q = s["question"].lower()
            profile = {"signals": dict(zip(s["signals"], WEIGHTS)), "vendors": [v for v in VENDORS if v in q]}
            owned = {t["name"].lower() for t in s["tools"]}
            mine = [{"id": f"installed:{t['name']}", "kind": t["kind"], "name": t["name"], "description": t["description"],
                     "category": "", "official": False, "install": "", "url": "", "have": True, "where": t["where"]}
                    for t in s["tools"]]
            pool = [it for it in s["items"] if it["name"].lower() not in owned] + mine
            ranked = score_items(pool, profile, owned, {}, keep_installed=True)
            for r in ranked:  # 아침과 달리 '몇 회'가 아니라 '어떤 작업과 관련'인지 보여 준다
                r["reason"] = "관련 작업: " + " · ".join(SIGNALS[k][0] for k in r["signals"])
            # 이미 가진 도구는 가장 중요한 작업과 직접 관련 있을 때만 알려 준다
            have = [r for r in ranked if r.get("have") and s["signals"][0] in r["signals"]][:3]
            ranked = [r for r in ranked if not r.get("have")]
            names = ", ".join(h["name"] for h in have) or "없음"
            bus.emit("inspector", "work", f"이미 가진 도구 {len(have)}개: {names}")
        else:
            have, ranked = s["have"], s["ranked"]
            bus.emit("inspector", "start", f"재검토 {rnd}차 — 다음 후보 묶음 꺼내는 중")
        cands = ranked[rnd * BATCH:(rnd + 1) * BATCH]
        bus.emit("inspector", "done", f"설치 후보 {len(cands)}개: {', '.join(c['name'] for c in cands) or '없음'}")
        bus.emit("inspector", "handoff", "검증팀에 확인 요청")
        return {"have": have, "ranked": ranked, "candidates": cands, "round": rnd + 1}

    def verifier(s: ChatState) -> dict:
        passed, warned, rejected = verify_batch(bus, checker, s)
        if enough_passed({**s, "passed": passed}, CHAT_TOP):
            bus.emit("verifier", "done", f"통과 {len(passed)} · 경고 {len(warned)} · 탈락 {len(rejected)}")
            bus.emit("verifier", "handoff", "상담팀에 전달")
        else:
            bus.emit("verifier", "retry", f"통과 {len(passed)}개뿐 — 점검팀에 후보 더 요청")
        return {"passed": passed, "warned": warned, "rejected": rejected}

    def answer(s: ChatState) -> dict:
        bus.emit("consultant", "start", "준비물 체크리스트 정리 중")

        def pack(rows):
            return [{k: r.get(k) for k in FIELDS} | {"guide": guide_for(r)} for r in rows]

        have = pack(s.get("have", []))
        install = pack(s.get("passed", [])[:CHAT_TOP])
        optional = pack((s.get("passed", [])[CHAT_TOP:] + s.get("warned", []))[:2])
        text = compose(s["question"], s.get("task", ""), have, install, optional, s.get("engine", "단어 매칭"))
        bus.emit("consultant", "done", text)
        bus.emit("consultant", "result", "상담 완료", {
            "mode": "chat", "question": s["question"], "task": s.get("task", ""), "engine": s.get("engine", ""),
            "answer": text, "have": have, "install": install, "optional": optional,
        })
        return {"answer": text}

    g = StateGraph(ChatState)
    for name, fn in (("intake", intake), ("collector", collector), ("inspector", inspector),
                     ("verifier", verifier), ("answer", answer)):
        g.add_node(name, fn)
    g.add_edge(START, "intake")
    g.add_conditional_edges("intake", lambda s: "collector" if s.get("signals") else "answer",
                            {"collector": "collector", "answer": "answer"})
    g.add_edge("collector", "inspector")
    g.add_edge("inspector", "verifier")
    g.add_conditional_edges("verifier", lambda s: "answer" if enough_passed(s, CHAT_TOP) else "inspector",
                            {"inspector": "inspector", "answer": "answer"})
    g.add_edge("answer", END)
    return g.compile()


def run_chat(bus: EventBus, data_dir: Path, question: str) -> dict:
    return build_chat_graph(bus, data_dir).invoke({"question": question, "round": 0}, {"recursion_limit": 30})

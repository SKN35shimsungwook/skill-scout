"""부서형 멀티 에이전트 흐름 (LangGraph).

수집기 → 점검팀 → 검증팀 ─(통과 후보 부족)→ 점검팀 재검토
                         └(충분)→ 브리핑팀 → 상담팀
각 부서는 규칙 기반이라 LLM 토큰을 쓰지 않는다. 진행 상황은 EventBus로 알린다.
"""
from pathlib import Path
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from . import briefing, catalog
from .events import EventBus
from .installed import installed_names
from .profile import build_profile
from .recommend import score_items
from .signals import SIGNALS
from .verify import RepoChecker, verify

BATCH = 4      # 점검팀이 한 번에 검증팀으로 넘기는 후보 수 (재검토 때마다 다음 묶음)
MAX_ROUNDS = 4


class State(TypedDict, total=False):
    days: int
    top: int
    recent: dict
    seen: list
    profile: dict
    items: list
    errors: list
    ranked: list
    round: int
    candidates: list
    passed: list
    warned: list
    rejected: list
    picks: list
    new_hits: list
    new_total: int
    text: str
    summary: str


def build_graph(bus: EventBus, data_dir: Path):
    checker = RepoChecker(data_dir / "github_cache.json")

    def collector(s: State) -> dict:
        bus.emit("collector", "start", "출근! 내 대화 기록을 읽는 중")
        profile = build_profile(s["days"])
        top = " · ".join(f"{SIGNALS[k][0]} {v}" for k, v in list(profile["signals"].items())[:3])
        bus.emit("collector", "work", f"대화 {profile['messages']}개 분석 완료 — {top}", {"signals": profile["signals"]})
        bus.emit("collector", "work", "공식 마켓·Anthropic 스킬·skills.sh에서 후보 모으는 중")
        items, errors = catalog.collect(data_dir)
        for e in errors:
            bus.emit("collector", "work", f"⚠️ {e}")
        bus.emit("collector", "done", f"후보 {len(items)}개 수집 완료")
        bus.emit("collector", "handoff", "점검팀에 전달")
        return {"profile": profile, "items": items, "errors": errors}

    def inspector(s: State) -> dict:
        rnd = s.get("round", 0)
        if rnd == 0:
            bus.emit("inspector", "start", "내 작업과 겹치는 후보를 찾는 중")
            ranked = score_items(s["items"], s["profile"], installed_names(), s.get("recent", {}))
            bus.emit("inspector", "work", f"관련 후보 {len(ranked)}개 · 이미 가진 건 제외")
        else:
            ranked = s["ranked"]
            bus.emit("inspector", "start", f"재검토 {rnd}차 — 다음 후보 묶음 꺼내는 중")
        cands = ranked[rnd * BATCH:(rnd + 1) * BATCH]
        names = ", ".join(c["name"] for c in cands) or "없음"
        bus.emit("inspector", "done", f"후보 {len(cands)}개 선정: {names}", {"candidates": [c["name"] for c in cands]})
        bus.emit("inspector", "handoff", "검증팀에 확인 요청")
        return {"ranked": ranked, "candidates": cands, "round": rnd + 1}

    def verifier(s: State) -> dict:
        bus.emit("verifier", "start", f"후보 {len(s['candidates'])}개 출처·관리 상태 확인 중")
        passed, warned, rejected = list(s.get("passed", [])), list(s.get("warned", [])), list(s.get("rejected", []))
        for c in s["candidates"]:
            verdict, why = verify(c, checker)
            c = {**c, "verdict": verdict, "verdict_note": why}
            {"PASS": passed, "WARNING": warned, "FAIL": rejected}[verdict].append(c)
            icon = {"PASS": "✅", "WARNING": "⚠️", "FAIL": "❌"}[verdict]
            bus.emit("verifier", "work", f"{icon} {c['name']} — {why}", {"name": c["name"], "verdict": verdict})
        checker.save()
        enough = len(passed) >= s["top"] or s["round"] >= MAX_ROUNDS or s["round"] * BATCH >= len(s["ranked"])
        if enough:
            bus.emit("verifier", "done", f"통과 {len(passed)} · 경고 {len(warned)} · 탈락 {len(rejected)}")
            bus.emit("verifier", "handoff", "브리핑팀에 전달")
        else:
            bus.emit("verifier", "retry", f"통과 {len(passed)}개뿐 — 점검팀에 후보 더 요청")
        return {"passed": passed, "warned": warned, "rejected": rejected}

    def route(s: State) -> str:
        enough = len(s["passed"]) >= s["top"] or s["round"] >= MAX_ROUNDS or s["round"] * BATCH >= len(s["ranked"])
        return "briefer" if enough else "inspector"

    def briefer(s: State) -> dict:
        bus.emit("briefer", "start", "아침 브리핑 작성 중")
        pool = s["passed"] + s["warned"]  # 통과한 것 먼저, 모자라면 경고 표시를 달고 채운다
        seen = set(s.get("seen") or [])
        first_run = not seen
        new_ids = set() if first_run else {it["id"] for it in s["items"]} - seen
        new_hits = [r for r in s["ranked"] if r["id"] in new_ids][:3]
        picks = pool[: s["top"]]
        text = briefing.build(s["profile"], picks, new_hits, len(new_ids), s.get("errors", []))
        if first_run:
            text += f"\n\n(첫 실행: 후보 {len(s['items'])}개를 기준으로 저장했어요. 다음부터 새로 나온 것을 따로 알려 드려요.)"
        bus.emit("briefer", "done", f"추천 {len(picks)}개 · 새 항목 {len(new_ids)}개 정리 완료")
        bus.emit("briefer", "handoff", "상담팀에 전달")
        return {"picks": picks, "new_hits": new_hits, "new_total": len(new_ids), "text": text}

    def consultant(s: State) -> dict:
        bus.emit("consultant", "start", "오늘 브리핑 요약 중")
        if s["picks"]:
            top_signal = SIGNALS[s["picks"][0]["signals"][0]][0]
            summary = f"요즘 '{top_signal}' 작업이 많아서 {s['picks'][0]['name']}부터 써 보시길 추천해요. 설치는 직접 승인해 주세요!"
        else:
            summary = "오늘은 새로 추천할 만한 게 없어요."
        bus.emit("consultant", "done", summary)
        bus.emit("consultant", "result", "브리핑 완료", {
            "picks": [{k: p.get(k) for k in ("name", "kind", "official", "description", "reason", "install", "url",
                                             "verdict", "verdict_note")} for p in s["picks"]],
            "rejected": [{"name": r["name"], "note": r["verdict_note"]} for r in s.get("rejected", [])],
            "summary": summary,
        })
        return {"summary": summary}

    g = StateGraph(State)
    for name, fn in (("collector", collector), ("inspector", inspector), ("verifier", verifier),
                     ("briefer", briefer), ("consultant", consultant)):
        g.add_node(name, fn)
    g.add_edge(START, "collector")
    g.add_edge("collector", "inspector")
    g.add_edge("inspector", "verifier")
    g.add_conditional_edges("verifier", route, {"inspector": "inspector", "briefer": "briefer"})
    g.add_edge("briefer", "consultant")
    g.add_edge("consultant", END)
    return g.compile()


def run_graph(bus: EventBus, data_dir: Path, days: int, top: int, recent: dict, seen: list) -> dict[str, Any]:
    app = build_graph(bus, data_dir)
    return app.invoke({"days": days, "top": top, "recent": recent, "seen": seen, "round": 0},
                      {"recursion_limit": 30})

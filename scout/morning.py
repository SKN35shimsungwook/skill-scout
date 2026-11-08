"""아침 브리핑의 '도구 추천' 외 섹션들 (모두 규칙 기반, 토큰 0).

1. 📂 어제 작업 브리핑      — 대화 기록 + Git
2. 🩺 상태 점검              — 마감 D-day, GitHub(push 안 한 커밋·Actions 실패), 배포 앱 응답
3. 📊 사용량·습관 팁·업데이트 — 어제 토큰, 습관 팁, Claude Code 새 버전
4. 📝 주간 요약 (월요일)      — 지난주 작업·커밋, 대화 정리 추천
"""
import json
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from pathlib import Path

import requests

from .worklog import Session, day_window, read_sessions

DESKTOP = Path.home() / "Desktop"
MEMORY_ROOT = Path.home() / ".claude" / "projects"
UA = {"User-Agent": "skill-scout"}
APP_RE = re.compile(r"https?://[\w.-]+\.(?:streamlit\.app|onrender\.com|github\.io|vercel\.app|netlify\.app)[^\s)\"'<>\]]*")


def _run(args: list[str], cwd: Path | None = None, timeout: int = 20) -> str:
    try:
        r = subprocess.run(args, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="ignore", timeout=timeout)
        return r.stdout.strip() if r.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def kor(n: int) -> str:
    if n >= 1e8:
        return f"{n / 1e8:.1f}억"
    if n >= 1e4:
        return f"{n / 1e4:.0f}만"
    return f"{n:,}"


def _short(text: str, n: int) -> str:
    return text if len(text) <= n else text[: n - 1] + "…"


# ---------- Git ----------
def git_state(repo: Path) -> dict:
    """커밋 안 한 변경(추적 중인 파일)과 push 안 한 커밋 수."""
    if not (repo / ".git").exists():
        return {}
    changed = [l for l in _run(["git", "status", "--porcelain"], repo).splitlines() if l and not l.startswith("??")]
    ahead = _run(["git", "rev-list", "--count", "@{u}..HEAD"], repo)
    return {"changed": len(changed), "ahead": int(ahead) if ahead.isdigit() else 0}


def desktop_repos() -> list[Path]:
    return [p for p in DESKTOP.iterdir() if p.is_dir() and (p / ".git").exists()]


# ---------- 1. 어제 작업 ----------
def yesterday_section(sessions: list[Session], day: date) -> str:
    lines = [f"**📂 어제 작업 브리핑** ({day:%m/%d})"]
    if not sessions:
        return "\n".join(lines + ["어제는 Claude로 작업한 기록이 없어요."])
    total = sum(len(s.requests) for s in sessions)
    lines.append(f"대화 {len(sessions)}개 · 내 요청 {total}개")
    todo: list[str] = []
    for s in sessions[:8]:
        projs = [p.name for p in s.projects][:2]
        where = f" · {', '.join(projs)}" if projs else ""
        lines.append(f"\n• **{_short(s.title, 40)}**{where} (요청 {len(s.requests)}개)")
        lines.append(f"   ↳ 마지막 요청: {_short(s.requests[-1], 70)}")
        if s.ended_by == "limit":
            lines.append("   ↳ ⏸ 사용 한도로 멈춘 채 끝남 → 이어서 하기")
            todo.append(f"'{_short(s.title, 24)}' 이어서 하기 (한도로 멈춤)")
        elif s.ended_by == "interrupted":
            lines.append("   ↳ ⏹ 중간에 멈춘 채 끝남")
        if s.pending:
            lines.append(f"   ↳ 남은 할 일: {_short(' · '.join(s.pending[:3]), 90)}")
            todo.append(f"{_short(s.title, 24)}: {_short(s.pending[0], 40)}")
        for repo in s.projects[:2]:
            g = git_state(repo)
            if g.get("changed") or g.get("ahead"):
                bits = [f"커밋 안 한 변경 {g['changed']}개"] * bool(g.get("changed")) + [f"push 안 한 커밋 {g['ahead']}개"] * bool(g.get("ahead"))
                lines.append(f"   ↳ {repo.name}: {' · '.join(bits)}")
                todo.append(f"{repo.name} {' · '.join(bits)} 정리")
    if len(sessions) > 8:
        lines.append(f"\n외 {len(sessions) - 8}개 대화")
    if todo:
        lines.append("\n**오늘 이어서 할 것**")
        lines += [f"{i}. {t}" for i, t in enumerate(dict.fromkeys(todo), 1)][:6]
    return "\n".join(lines)


# ---------- 2. 상태 점검 ----------
def deadlines(today: date, extra_file: Path) -> list[tuple[int, str]]:
    """메모리에 적힌 '마감 YYYY-MM-DD' + data/deadlines.json([{"name","date"}])에서 30일 안의 마감."""
    found: dict[str, date] = {}
    for d in MEMORY_ROOT.glob("*/memory"):
        # 목차(MEMORY.md)를 먼저 읽어 사람이 읽기 좋은 이름을 쓰고, 같은 날짜의 중복은 건너뛴다
        for f in sorted(d.glob("*.md"), key=lambda p: p.name != "MEMORY.md"):
            for line in f.read_text(encoding="utf-8", errors="ignore").splitlines():
                m = re.search(r"마감\s*(\d{4}-\d{2}-\d{2})", line)
                if m:
                    label = re.search(r"\[([^\]]+)\]", line)
                    name = label.group(1) if label else f.stem
                    when = date.fromisoformat(m.group(1))
                    if when not in found.values():
                        found[name] = when
    if extra_file.exists():
        for row in json.loads(extra_file.read_text(encoding="utf-8")):
            found[row["name"]] = date.fromisoformat(row["date"])
    out = [((d - today).days, n) for n, d in found.items() if 0 <= (d - today).days <= 30]
    return sorted(out)


def github_status() -> tuple[list[str], list[str]]:
    """(Actions 실패 저장소, push 안 한 커밋이 있는 로컬 저장소)."""
    failed = []
    raw = _run(["gh", "api", "user/repos?sort=pushed&per_page=12"], timeout=30)
    repos = json.loads(raw) if raw else []
    recent = [r for r in repos if r.get("pushed_at", "") >= (datetime.utcnow() - timedelta(days=14)).isoformat()]
    for r in recent:
        out = _run(["gh", "api", f"repos/{r['full_name']}/actions/runs?per_page=1"], timeout=20)
        runs = json.loads(out).get("workflow_runs", []) if out else []
        if runs and runs[0].get("conclusion") == "failure":
            failed.append(f"{r['name']} ({runs[0].get('name', 'workflow')})")
    ahead = []
    for repo in desktop_repos():
        g = git_state(repo)
        if g.get("ahead"):
            ahead.append(f"{repo.name} {g['ahead']}개")
    return failed, ahead


def app_urls() -> list[str]:
    """배포 앱 주소: 바탕화면 저장소 README에 적힌 Streamlit·Render·Pages 등 링크."""
    urls = []
    for repo in desktop_repos():
        readme = repo / "README.md"
        if readme.exists():
            urls += APP_RE.findall(readme.read_text(encoding="utf-8", errors="ignore"))
    clean = [u.rstrip(".,*_`") for u in urls if "githubusercontent" not in u]
    return list(dict.fromkeys(clean))[:20]


def check_app(url: str) -> tuple[str, str]:
    try:
        r = requests.get(url, headers=UA, timeout=20, allow_redirects=True)
        if r.status_code < 400:
            return url, "ok"
        return url, f"오류 {r.status_code}"
    except requests.Timeout:
        return url, "응답 느림 (잠든 상태일 수 있음)"
    except requests.RequestException:
        return url, "접속 안 됨"


def status_section(today: date, data_dir: Path) -> str:
    lines = ["**🩺 상태 점검**"]
    dl = deadlines(today, data_dir / "deadlines.json")
    if dl:
        lines.append("⏰ " + " · ".join(f"{n} D-{d}" if d else f"{n} 오늘 마감!" for d, n in dl))
    else:
        lines.append("⏰ 30일 안에 마감 없음 (추가: data/deadlines.json)")
    failed, ahead = github_status()
    lines.append("🐙 Actions 실패: " + (", ".join(failed) if failed else "없음"))
    lines.append("🐙 push 안 한 커밋: " + (", ".join(ahead) if ahead else "없음"))
    urls = app_urls()
    if urls:
        with ThreadPoolExecutor(8) as ex:
            results = list(ex.map(check_app, urls))
        bad = [(u, s) for u, s in results if s != "ok"]
        lines.append(f"🌐 배포 앱 {len(results)}개 중 정상 {len(results) - len(bad)}개")
        lines += [f"   ↳ {re.sub(r'^https?://', '', u)[:60]} — {s}" for u, s in bad[:6]]
    return "\n".join(lines)


# ---------- 3. 사용량·습관 팁·업데이트 ----------
def latest_release(repo: str = "anthropics/claude-code") -> dict:
    out = _run(["gh", "api", f"repos/{repo}/releases?per_page=1"], timeout=20)
    rels = json.loads(out) if out else []
    return rels[0] if rels else {}


def usage_section(sessions: list[Session], state: dict) -> str:
    lines = ["**📊 사용량 · 습관 팁 · 업데이트**"]
    tot = {k: sum(s.tokens[k] for s in sessions) for k in ("input", "output", "cache_read", "cache_write")}
    lines.append(f"어제 토큰: 출력 {kor(tot['output'])} · 캐시 읽기 {kor(tot['cache_read'])} · 캐시 쓰기 {kor(tot['cache_write'])}")
    big = max(sessions, key=lambda s: s.tokens["cache_read"], default=None)
    if big and tot["cache_read"]:
        share = big.tokens["cache_read"] / tot["cache_read"] * 100
        lines.append(f"가장 많이 쓴 대화: {_short(big.title, 30)} (캐시 읽기의 {share:.0f}%)")

    tips = []
    for s in sessions:
        if s.tokens["cache_read"] > 300_000_000:
            tips.append(f"'{_short(s.title, 24)}' 대화가 길어요 (캐시 읽기 {kor(s.tokens['cache_read'])}). 정리 요약을 받고 새 대화로 이어 가면 토큰이 줄어요")
    pdf = sum(s.pdf_reads for s in sessions)
    if pdf:
        tips.append(f"PDF를 그대로 읽은 적 {pdf}번 → markitdown으로 먼저 변환하면 토큰이 줄어요")
    brev = sum(s.brevity for s in sessions)
    if brev >= 2:
        tips.append(f"'간단히·핵심만' 요청 {brev}번 → 간결한 답을 기본 규칙으로 정해 두면 매번 말하지 않아도 돼요")
    stops = sum(s.interrupts for s in sessions)
    if stops >= 3:
        tips.append(f"중간에 멈춘 횟수 {stops}번 → 처음 요청에 범위·형식을 같이 적으면 줄일 수 있어요")
    lines.append("💡 " + ("\n💡 ".join(tips) if tips else "어제는 특별히 고칠 습관이 없어요"))

    rel = latest_release()
    if rel:
        tag = rel.get("tag_name", "")
        if tag and tag != state.get("claude_code_release"):
            notes = [l.strip("-* ").strip() for l in (rel.get("body") or "").splitlines() if l.strip().startswith(("-", "*"))][:3]
            lines.append(f"🔄 Claude Code 새 버전 {tag}" + "".join(f"\n   ↳ {_short(n, 80)}" for n in notes))
            state["claude_code_release_pending"] = tag  # 실제로 보냈을 때만 '알림 완료'로 기록
        else:
            lines.append(f"🔄 Claude Code 최신 {tag} (새 버전 없음)")
    return "\n".join(lines)


# ---------- 4. 주간 요약 ----------
def _similar(a: str, b: str) -> float:
    ta, tb = set(re.findall(r"\w+", a.lower())), set(re.findall(r"\w+", b.lower()))
    return len(ta & tb) / len(ta | tb) if ta and tb else 0.0


def weekly_section(today: date) -> str:
    end = datetime.combine(today, datetime.min.time())
    start = end - timedelta(days=7)
    sessions = read_sessions(start, end)
    lines = [f"**📝 지난주 요약** ({start:%m/%d}~{(end - timedelta(days=1)):%m/%d})",
             f"대화 {len(sessions)}개 · 내 요청 {sum(len(s.requests) for s in sessions)}개"]
    by_proj: dict[str, int] = {}
    for s in sessions:
        for p in s.projects[:1] or [Path(s.title)]:
            by_proj[p.name] = by_proj.get(p.name, 0) + len(s.requests)
    top = sorted(by_proj.items(), key=lambda x: -x[1])[:6]
    lines.append("많이 한 작업: " + " · ".join(f"{n}({c})" for n, c in top))

    commits = []
    for repo in desktop_repos():
        n = _run(["git", "log", "--since=7 days ago", "--oneline"], repo)
        if n:
            commits.append((repo.name, len(n.splitlines())))
    commits.sort(key=lambda x: -x[1])
    lines.append("커밋: " + (" · ".join(f"{n} {c}개" for n, c in commits[:6]) if commits else "없음"))

    unfinished = [s for s in sessions if s.pending or s.ended_by == "limit"]
    if unfinished:
        lines.append("못 끝낸 작업: " + " · ".join(_short(s.title, 20) for s in unfinished[:5]))

    groups, used = [], set()
    for i, a in enumerate(sessions):
        if i in used:
            continue
        g = [a] + [b for j, b in enumerate(sessions[i + 1:], i + 1) if j not in used and _similar(a.title, b.title) >= 0.5]
        if len(g) > 1:
            used |= {sessions.index(x) for x in g}
            groups.append(g)
    small = [s for s in sessions if len(s.requests) <= 2]
    lines.append(f"🗂 대화 정리 추천: 비슷한 대화 {len(groups)}묶음 · 요청 2개 이하 짧은 대화 {len(small)}개(보관 후보)")
    lines += [f"   ↳ {' / '.join(_short(x.title, 18) for x in g[:3])}" for g in groups[:3]]
    lines.append("주간회고 쓸 때 이 요약을 재료로 쓰세요.")
    return "\n".join(lines)


def build_sections(data_dir: Path, state: dict, bus=None, weekly: bool | None = None) -> list[str]:
    """어제 작업 · 상태 점검 · 사용량 섹션(+ 월요일 주간 요약)을 만든다. bus가 있으면 부서 진행 상황을 알린다."""
    emit = bus.emit if bus else (lambda *a, **k: None)
    today = date.today()
    yday = datetime.combine(today - timedelta(days=1), datetime.min.time())
    emit("collector", "start", "어제 작업 기록 읽는 중")
    sessions = read_sessions(*day_window(yday))
    emit("collector", "done", f"어제 대화 {len(sessions)}개 확인")
    emit("inspector", "start", "남은 할 일·끊긴 작업·Git 상태 점검 중")
    sections = [yesterday_section(sessions, yday.date())]
    emit("inspector", "work", "마감·GitHub·배포 앱 점검 중")
    sections.append(status_section(today, data_dir))
    sections.append(usage_section(sessions, state))
    if weekly or (weekly is None and today.weekday() == 0):
        emit("inspector", "work", "지난주 요약 정리 중")
        sections.append(weekly_section(today))
    emit("inspector", "done", f"아침 점검 섹션 {len(sections)}개 완료")
    return sections

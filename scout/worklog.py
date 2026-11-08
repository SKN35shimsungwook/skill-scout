"""Claude Code 대화 기록에서 '언제 무슨 작업을 했고 무엇이 남았는지'를 뽑는다.

원문은 PC 밖으로 나가지 않는다. 결과는 세션별 제목·요청 몇 줄·남은 할 일·토큰 수치다.
"""
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

PROJECTS_DIR = Path.home() / ".claude" / "projects"
SKIP_PREFIX = ("<system-reminder", "<command-", "<local-command", "<task-notification", "<side-sessions-event",
               "<artifact-view-context", "[Request interrupted",
               "This session is being continued")  # 긴 대화 이어 가기 자동 요약
LIMIT_RE = re.compile(r"(usage limit|limit reached|rate limit|5-hour limit|weekly limit|한도)", re.I)
BREVITY_RE = re.compile(r"(핵심만|간략|짧게|요약만|간단히)")


@dataclass
class Session:
    id: str
    title: str = ""
    cwd: str = ""
    first: datetime | None = None
    last: datetime | None = None
    requests: list[str] = field(default_factory=list)   # 기간 안에 내가 쓴 요청 (앞부분만)
    plan: list[dict] = field(default_factory=list)      # 마지막 할 일 목록
    plan_closed: bool = False                           # 마지막 목록 뒤에 마무리(wrap_up)가 있었는지
    ended_by: str = ""                                  # limit · interrupted · ""
    tokens: dict = field(default_factory=lambda: {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0})
    pdf_reads: int = 0
    brevity: int = 0
    interrupts: int = 0
    files: set = field(default_factory=set)              # 수정한 파일 경로

    @property
    def pending(self) -> list[str]:
        if self.plan_closed:
            return []
        return [p.get("content", "") for p in self.plan if p.get("status") != "completed"]

    @property
    def folder(self) -> str:
        return Path(self.cwd).name if self.cwd else ""

    @property
    def projects(self) -> list[Path]:
        """수정한 파일이 속한 프로젝트 폴더 (바탕화면 바로 아래 폴더 기준, 많이 고친 순)."""
        desk = Path.home() / "Desktop"
        count: dict[Path, int] = {}
        for f in self.files:
            p = Path(f)
            try:
                rel = p.resolve().relative_to(desk.resolve())
            except (ValueError, OSError):
                continue
            if len(rel.parts) < 2 or any(part.startswith(".") for part in rel.parts[:2]):
                continue  # 설정 폴더(.claude 등)는 프로젝트가 아님
            root = desk / rel.parts[0]
            if rel.parts[0] == "skn35 report" and len(rel.parts) > 2:  # 수업 폴더 안의 하위 프로젝트
                root = root / rel.parts[1]
            count[root] = count.get(root, 0) + 1
        return sorted(count, key=lambda r: -count[r])


def _local(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone().replace(tzinfo=None)


def _text(content) -> str:
    if isinstance(content, list):
        return " ".join(c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text")
    return content if isinstance(content, str) else ""


def _apply_plan(sess: Session, inp: dict) -> None:
    """앱의 할 일 목록(update_plan) 변경을 따라가며 마지막 상태를 만든다."""
    if inp.get("items"):
        sess.plan = [dict(i) for i in inp["items"]]
        sess.plan_closed = False
        return
    if inp.get("advance"):
        cur = next((i for i, p in enumerate(sess.plan) if p.get("status") == "in_progress"), None)
        if cur is not None:
            sess.plan[cur]["status"] = "completed"
            nxt = next((i for i, p in enumerate(sess.plan) if p.get("status") == "pending"), None)
            if nxt is not None:
                sess.plan[nxt]["status"] = "in_progress"
    for n in inp.get("done") or []:
        if 0 < n <= len(sess.plan):
            sess.plan[n - 1]["status"] = "completed"
    if inp.get("start") and 0 < inp["start"] <= len(sess.plan):
        sess.plan[inp["start"] - 1]["status"] = "in_progress"


def read_sessions(start: datetime, end: datetime) -> list[Session]:
    """start~end(로컬 시각) 사이에 내가 메시지를 보낸 세션들."""
    out = []
    for path in PROJECTS_DIR.glob("*/*.jsonl"):
        if datetime.fromtimestamp(path.stat().st_mtime) < start:
            continue
        sess = Session(id=path.stem)
        seen_msg: dict[str, dict] = {}
        last_kind = ""
        with path.open(encoding="utf-8", errors="ignore") as f:
            for line in f:
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                t = d.get("type")
                if t == "custom-title":
                    sess.title = d.get("customTitle") or sess.title
                    continue
                ts = d.get("timestamp")
                if not ts or t not in ("user", "assistant"):
                    continue
                when = _local(ts)
                if not (start <= when < end):
                    continue
                sess.cwd = d.get("cwd") or sess.cwd
                msg = d.get("message") or {}
                if t == "user" and not d.get("isMeta"):
                    text = _text(msg.get("content")).strip()
                    if text.startswith("[Request interrupted"):
                        sess.interrupts += 1
                        last_kind = "interrupted"
                    elif text and not text.lstrip().startswith(SKIP_PREFIX):
                        sess.requests.append(" ".join(text.split())[:120])
                        sess.brevity += bool(BREVITY_RE.search(text[:300]))
                        sess.first = sess.first or when
                        sess.last = when
                        last_kind = ""
                elif t == "assistant":
                    if d.get("isApiErrorMessage") and LIMIT_RE.search(_text(msg.get("content"))):
                        last_kind = "limit"
                    if msg.get("id") and msg.get("usage"):
                        seen_msg[msg["id"]] = msg["usage"]  # 같은 응답이 여러 줄에 나뉘어 저장되므로 마지막 값만
                    for c in msg.get("content") or []:
                        if not isinstance(c, dict) or c.get("type") != "tool_use":
                            continue
                        name, inp = c.get("name", ""), c.get("input") or {}
                        if name.endswith("update_plan"):
                            _apply_plan(sess, inp)
                        elif name.endswith("wrap_up") or name == "TodoWrite" and all(
                                x.get("status") == "completed" for x in inp.get("todos", [])):
                            sess.plan_closed = True
                        elif name == "TodoWrite":
                            sess.plan = [{"content": x.get("content", ""), "status": x.get("status")} for x in inp.get("todos", [])]
                            sess.plan_closed = False
                        elif name in ("Write", "Edit", "NotebookEdit") and inp.get("file_path"):
                            sess.files.add(str(inp["file_path"]))
                        elif name == "Read" and str(inp.get("file_path", "")).lower().endswith(".pdf"):
                            sess.pdf_reads += 1
                    if not d.get("isApiErrorMessage"):
                        last_kind = ""  # 이후에 응답이 이어졌으면 끊긴 게 아님
        if not sess.requests:
            continue
        for u in seen_msg.values():
            sess.tokens["input"] += u.get("input_tokens", 0) or 0
            sess.tokens["output"] += u.get("output_tokens", 0) or 0
            sess.tokens["cache_read"] += u.get("cache_read_input_tokens", 0) or 0
            sess.tokens["cache_write"] += u.get("cache_creation_input_tokens", 0) or 0
        sess.ended_by = last_kind
        sess.title = sess.title or sess.requests[0][:40]
        out.append(sess)
    out.sort(key=lambda s: s.last or start, reverse=True)
    return out


def day_window(day: datetime) -> tuple[datetime, datetime]:
    start = day.replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=1)

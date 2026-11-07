"""이미 가지고 있는 스킬·플러그인을 모은다.

아침 추천에서는 빼는 데 쓰고, 채팅 상담에서는 '이미 있어요'로 보여 주는 데 쓴다.
"""
import json
from pathlib import Path

CLAUDE = Path.home() / ".claude"
APP_DATA = Path.home() / "AppData" / "Local" / "Claude-Data"


def _skill_description(skill_md: Path) -> str:
    try:
        raw = skill_md.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""
    if not raw.startswith("---"):
        return ""
    for line in raw.split("---", 2)[1].splitlines():
        if line.strip().startswith("description:"):
            return line.split(":", 1)[1].strip().strip('"')
    return ""


def installed_tools() -> list[dict]:
    """[{name, kind, where, description}] — where: 내 스킬 폴더 · Claude 앱 · Claude Code"""
    tools: dict[str, dict] = {}
    skills_dir = CLAUDE / "skills"
    if skills_dir.exists():
        for p in skills_dir.iterdir():
            if p.is_dir():
                tools[p.name.lower()] = {"name": p.name, "kind": "스킬", "where": "내 스킬 폴더",
                                         "description": _skill_description(p / "SKILL.md")}
    # Claude 데스크톱 앱이 기본으로 넣어 주거나 앱에서 설치한 스킬(pdf, docx, xlsx, pptx 등)
    if APP_DATA.exists():
        for p in APP_DATA.rglob("SKILL.md"):
            if p.parent.name.startswith("plugin_"):  # 플러그인 묶음 폴더 자체는 스킬 이름이 아님
                continue
            tools.setdefault(p.parent.name.lower(), {"name": p.parent.name, "kind": "스킬", "where": "Claude 앱",
                                                     "description": _skill_description(p)})
    plugins_file = CLAUDE / "plugins" / "installed_plugins.json"
    if plugins_file.exists():
        data = json.loads(plugins_file.read_text(encoding="utf-8"))
        for key in (data.get("plugins") or data):
            name = str(key).split("@")[0]
            tools[name.lower()] = {"name": name, "kind": "플러그인", "where": "Claude Code", "description": ""}
    settings = CLAUDE / "settings.json"
    if settings.exists():
        enabled = json.loads(settings.read_text(encoding="utf-8")).get("enabledPlugins") or {}
        for k, v in enabled.items():
            if v:
                name = k.split("@")[0]
                tools[name.lower()] = {"name": name, "kind": "플러그인", "where": "Claude Code", "description": ""}
    return sorted(tools.values(), key=lambda t: (t["kind"], t["name"]))


def installed_names() -> set[str]:
    return {t["name"].lower() for t in installed_tools()}

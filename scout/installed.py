"""이미 가지고 있는 스킬·플러그인을 모은다 (추천에서 빼고, 화면의 '내 도구'에 보여 주기 위해)."""
import json
from pathlib import Path

CLAUDE = Path.home() / ".claude"
APP_DATA = Path.home() / "AppData" / "Local" / "Claude-Data"


def installed_tools() -> list[dict]:
    """[{name, kind, where}] — where: 내가 만든 스킬 · 앱 기본 스킬 · 플러그인"""
    tools: dict[str, dict] = {}
    skills_dir = CLAUDE / "skills"
    if skills_dir.exists():
        for p in skills_dir.iterdir():
            if p.is_dir():
                tools[p.name.lower()] = {"name": p.name, "kind": "스킬", "where": "내 스킬 폴더"}
    # Claude 데스크톱 앱이 기본으로 넣어 주거나 앱에서 설치한 스킬(pdf, docx, xlsx, pptx 등)
    if APP_DATA.exists():
        for p in APP_DATA.rglob("SKILL.md"):
            if p.parent.name.startswith("plugin_"):  # 플러그인 묶음 폴더 자체는 스킬 이름이 아님
                continue
            tools.setdefault(p.parent.name.lower(), {"name": p.parent.name, "kind": "스킬", "where": "Claude 앱"})
    plugins_file = CLAUDE / "plugins" / "installed_plugins.json"
    if plugins_file.exists():
        data = json.loads(plugins_file.read_text(encoding="utf-8"))
        for key in (data.get("plugins") or data):
            name = str(key).split("@")[0]
            tools[name.lower()] = {"name": name, "kind": "플러그인", "where": "Claude Code"}
    settings = CLAUDE / "settings.json"
    if settings.exists():
        enabled = json.loads(settings.read_text(encoding="utf-8")).get("enabledPlugins") or {}
        for k, v in enabled.items():
            if v:
                name = k.split("@")[0]
                tools[name.lower()] = {"name": name, "kind": "플러그인", "where": "Claude Code"}
    return sorted(tools.values(), key=lambda t: (t["kind"], t["name"]))


def installed_names() -> set[str]:
    return {t["name"].lower() for t in installed_tools()}

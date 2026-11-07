"""이미 가지고 있는 스킬·플러그인 이름을 모은다 (추천에서 빼기 위해)."""
import json
from pathlib import Path

CLAUDE = Path.home() / ".claude"


def installed_names() -> set[str]:
    names: set[str] = set()
    skills_dir = CLAUDE / "skills"
    if skills_dir.exists():
        names |= {p.name.lower() for p in skills_dir.iterdir() if p.is_dir()}
    plugins_file = CLAUDE / "plugins" / "installed_plugins.json"
    if plugins_file.exists():
        data = json.loads(plugins_file.read_text(encoding="utf-8"))
        for key in (data.get("plugins") or data):
            names.add(str(key).split("@")[0].lower())
    # Claude 데스크톱 앱이 기본으로 넣어 주는 스킬(pdf, docx, xlsx, pptx 등)
    app_data = Path.home() / "AppData" / "Local" / "Claude-Data"
    if app_data.exists():
        names |= {p.parent.name.lower() for p in app_data.rglob("SKILL.md")}
    settings = CLAUDE / "settings.json"
    if settings.exists():
        enabled = json.loads(settings.read_text(encoding="utf-8")).get("enabledPlugins") or {}
        names |= {k.split("@")[0].lower() for k, v in enabled.items() if v}
    return names

"""추천 후보 목록을 모은다.

- 공식 플러그인 마켓 (anthropics/claude-plugins-official)
- Anthropic 공식 스킬 (anthropics/skills)
- skills.sh 인기 스킬 (첫 화면 순위표 + 개별 페이지 설명, 설명은 캐시)
"""
import json
import re
import time
from pathlib import Path

import requests

UA = {"User-Agent": "skill-scout (personal recommender)"}
GITHUB_RE = re.compile(r"github\.com[/:]([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?(?:/|$)")


def _github_repo(*candidates: str) -> str:
    for c in candidates:
        m = GITHUB_RE.search(c or "")
        if m:
            return f"{m.group(1)}/{m.group(2)}"
    return ""
LOCAL_MARKET = Path.home() / ".claude" / "plugins" / "marketplaces" / "claude-plugins-official" / ".claude-plugin" / "marketplace.json"
MARKET_URL = "https://raw.githubusercontent.com/anthropics/claude-plugins-official/main/.claude-plugin/marketplace.json"


def plugins() -> list[dict]:
    try:
        data = requests.get(MARKET_URL, headers=UA, timeout=30).json()
    except Exception:  # 인터넷이 안 되면 Claude Code가 받아 둔 사본 사용
        data = json.loads(LOCAL_MARKET.read_text(encoding="utf-8"))
    items = []
    for p in data.get("plugins", []):
        src = p.get("source") if isinstance(p.get("source"), dict) else {}
        items.append({
            "id": f"plugin:{p['name']}",
            "kind": "플러그인",
            "name": p["name"],
            "description": p.get("description", ""),
            "category": p.get("category") or "",
            "version": src.get("ref") or p.get("version") or "",
            "official": (p.get("author") or {}).get("name") == "Anthropic" or isinstance(p.get("source"), str),
            "install": f"/plugin install {p['name']}@claude-plugins-official",
            "url": p.get("homepage") or "",
            "repo": _github_repo(src.get("url", ""), f"github.com/{src['repo']}" if src.get("repo") else "", p.get("homepage", ""))
                    or ("anthropics/claude-plugins-official" if isinstance(p.get("source"), str) else ""),
        })
    return items


def anthropic_skills() -> list[dict]:
    repo = "anthropics/skills"
    tree = requests.get(f"https://api.github.com/repos/{repo}/git/trees/main?recursive=1", headers=UA, timeout=30).json()
    items = []
    for t in tree.get("tree", []):
        if not t["path"].endswith("SKILL.md"):
            continue
        raw = requests.get(f"https://raw.githubusercontent.com/{repo}/main/{t['path']}", headers=UA, timeout=30).text
        meta = {}
        if raw.startswith("---"):
            for line in raw.split("---", 2)[1].splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    meta[k.strip()] = v.strip().strip('"')
        name = meta.get("name") or Path(t["path"]).parent.name
        items.append({
            "id": f"skill:anthropic:{name}",
            "kind": "스킬",
            "name": name,
            "description": meta.get("description", ""),
            "category": "",
            "version": t.get("sha", "")[:7],
            "official": True,
            "install": f"npx skills add https://github.com/{repo} --skill {name}",
            "url": f"https://github.com/{repo}/tree/main/{Path(t['path']).parent.as_posix()}",
            "repo": repo,
        })
    return items


def skills_sh(cache_path: Path) -> list[dict]:
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
    html = requests.get("https://skills.sh/", headers=UA, timeout=30).text
    slugs = list(dict.fromkeys(re.findall(r'href="/([A-Za-z0-9_-]+/[A-Za-z0-9_.-]+/[A-Za-z0-9_.:-]+)"', html)))
    items = []
    for rank, slug in enumerate(slugs, 1):
        if slug not in cache:  # 처음 보는 스킬만 개별 페이지를 연다
            try:
                page = requests.get(f"https://skills.sh/{slug}", headers=UA, timeout=30).text
                desc = re.search(r'<meta name="description" content="([^"]*)"', page)
                cmd = re.search(r"(npx skills add [^<\"\\]+)", page)
                cache[slug] = {"description": desc.group(1) if desc else "", "install": cmd.group(1).strip() if cmd else ""}
            except requests.RequestException:
                continue
            time.sleep(0.4)
        owner, repo, name = slug.split("/", 2)
        items.append({
            "id": f"skill:skills.sh:{slug}",
            "kind": "스킬",
            "name": name,
            "description": cache[slug]["description"],
            "category": "",
            "version": "",
            "official": owner == "anthropics",
            "install": cache[slug]["install"] or f"npx skills add https://github.com/{owner}/{repo} --skill {name}",
            "url": f"https://skills.sh/{slug}",
            "rank": rank,
            "repo": f"{owner}/{repo}",
        })
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    return items


def collect(cache_dir: Path) -> tuple[list[dict], list[str]]:
    """모든 출처를 모은다. 한 출처가 실패해도 나머지는 쓴다."""
    items, errors = [], []
    for name, fn in (("공식 플러그인", plugins), ("Anthropic 스킬", anthropic_skills),
                     ("skills.sh", lambda: skills_sh(cache_dir / "skills_sh_cache.json"))):
        try:
            items += fn()
        except Exception as e:
            errors.append(f"{name}: {e}")
    return items, errors

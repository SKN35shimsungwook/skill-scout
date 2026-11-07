"""검증팀의 실제 검사: 추천 후보를 믿고 설치해도 되는지 확인한다.

- 설치 명령 형식이 맞는지
- GitHub 저장소가 실제로 있는지, 보관(archived) 처리되지 않았는지
- 1년 넘게 손대지 않은 저장소인지 (경고)
- 공식이 아닌데 별이 너무 적은지 (경고)
GitHub 조회 결과는 하루 동안 캐시한다.
"""
import json
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

INSTALL_RE = re.compile(r"^(/plugin install [\w.@-]+|npx skills add https://github\.com/[\w.-]+/[\w.-]+ --skill [\w.:-]+)$")
DAY = 24 * 3600


def _token() -> str:
    tok = os.getenv("GITHUB_TOKEN", "")
    if tok:
        return tok
    try:  # gh CLI에 로그인돼 있으면 그 토큰을 쓴다 (조회 한도 60 → 5,000회)
        return subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, timeout=10).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


class RepoChecker:
    def __init__(self, cache_path: Path):
        self.cache_path = cache_path
        self.cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
        tok = _token()
        self.headers = {"User-Agent": "skill-scout", **({"Authorization": f"Bearer {tok}"} if tok else {})}

    def info(self, repo: str) -> dict:
        hit = self.cache.get(repo)
        if hit and time.time() - hit["checked"] < DAY:
            return hit
        try:
            r = requests.get(f"https://api.github.com/repos/{repo}", headers=self.headers, timeout=20)
            if r.status_code == 404:
                data = {"exists": False}
            elif r.ok:
                j = r.json()
                data = {"exists": True, "archived": j.get("archived", False), "stars": j.get("stargazers_count", 0),
                        "pushed_at": j.get("pushed_at")}
            else:
                return {"exists": None}  # 한도 초과 등 확인 불가 — 캐시하지 않음
        except requests.RequestException:
            return {"exists": None}
        data["checked"] = time.time()
        self.cache[repo] = data
        return data

    def save(self) -> None:
        self.cache_path.write_text(json.dumps(self.cache, ensure_ascii=False, indent=1), encoding="utf-8")


def verify(item: dict, checker: RepoChecker) -> tuple[str, str]:
    """(판정, 이유) 반환. 판정: PASS · WARNING · FAIL"""
    if not INSTALL_RE.match(item.get("install", "")):
        return "FAIL", "설치 명령 형식이 이상함"
    repo = item.get("repo")
    if not repo:
        return ("PASS", "공식 마켓 등록") if item.get("official") else ("WARNING", "저장소를 확인할 수 없음")
    info = checker.info(repo)
    if info.get("exists") is None:
        return "WARNING", "GitHub 확인 실패 (나중에 다시 확인)"
    if not info["exists"]:
        return "FAIL", f"저장소 없음 ({repo})"
    if info.get("archived"):
        return "FAIL", "저장소가 보관 처리됨 (더 이상 관리 안 함)"
    days = (datetime.now(timezone.utc) - datetime.fromisoformat(info["pushed_at"].replace("Z", "+00:00"))).days if info.get("pushed_at") else 9999
    stars = info.get("stars", 0)
    if days > 365:
        return "WARNING", f"{days // 30}개월째 업데이트 없음"
    if not item.get("official") and stars < 10:
        return "WARNING", f"별 {stars}개 · 사용자가 적음"
    return "PASS", f"별 {stars:,}개 · {days}일 전 업데이트" + (" · 공식" if item.get("official") else "")

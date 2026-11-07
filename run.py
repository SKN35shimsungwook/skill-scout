"""skill-scout 실행 진입점.

python run.py            # 추천 계산 → 디스코드 전송 (DISCORD_WEBHOOK_URL 필요)
python run.py --dry-run  # 전송하지 않고 화면과 data/latest_briefing.md에만 출력
"""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

from scout import briefing, catalog
from scout.installed import installed_names
from scout.profile import build_profile
from scout.recommend import score_items

ROOT = Path(__file__).parent
DATA = ROOT / "data"
STATE = DATA / "state.json"


def load_state() -> dict:
    return json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {"seen": [], "recommended": {}}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--days", type=int, default=30, help="최근 며칠 대화를 볼지")
    ap.add_argument("--top", type=int, default=5)
    args = ap.parse_args()
    load_dotenv(ROOT / ".env")
    DATA.mkdir(exist_ok=True)

    state = load_state()
    week_ago = (datetime.now() - timedelta(days=7)).isoformat()
    recent = {k: v for k, v in state["recommended"].items() if v >= week_ago}

    profile = build_profile(args.days)
    items, errors = catalog.collect(DATA)
    ranked = score_items(items, profile, installed_names(), recent)

    first_run = not state["seen"]
    seen = set(state["seen"])
    new_ids = set() if first_run else {it["id"] for it in items} - seen
    new_hits = [r for r in ranked if r["id"] in new_ids][:3]
    picks = [r for r in ranked if r["id"] not in {n["id"] for n in new_hits}][: args.top]

    text = briefing.build(profile, picks, new_hits, len(new_ids), errors)
    if first_run:
        text += f"\n\n(첫 실행: 후보 {len(items)}개를 기준으로 저장했어요. 내일부터 새로 나온 것을 따로 알려 드려요.)"
    (DATA / "latest_briefing.md").write_text(text, encoding="utf-8")
    (DATA / "latest_ranking.json").write_text(json.dumps(ranked[:50], ensure_ascii=False, indent=1), encoding="utf-8")
    print(text)

    if not args.dry_run:
        url = os.getenv("DISCORD_WEBHOOK_URL")
        if not url:
            sys.exit("DISCORD_WEBHOOK_URL이 .env에 없어서 전송하지 않았어요. (--dry-run 결과는 data/latest_briefing.md)")
        briefing.send_discord(url, text)
        now = datetime.now().isoformat()
        state["recommended"].update({p["id"]: now for p in picks + new_hits})

    state["seen"] = sorted(seen | {it["id"] for it in items})
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()

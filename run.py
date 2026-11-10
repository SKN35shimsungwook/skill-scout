"""skill-scout 실행 진입점 (아침 자동 실행용).

python run.py            # 부서 흐름 실행 → 디스코드 전송 (DISCORD_WEBHOOK_URL 필요)
python run.py --dry-run  # 전송하지 않고 화면과 data/latest_briefing.md에만 출력
python office.py         # 2D 오피스 화면에서 부서들이 일하는 모습을 보며 실행
"""
import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

from scout.events import EventBus
from scout.pipeline import execute, should_skip_scheduled


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--days", type=int, default=30, help="최근 며칠 대화를 볼지")
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--verbose", action="store_true", help="부서별 진행 상황 출력")
    ap.add_argument("--weekly", action="store_true", help="이번 주에 이미 보냈어도 지난주 요약 포함")
    ap.add_argument("--scheduled", action="store_true", help="자동 실행용: 오늘 이미 보냈거나 새벽이면 건너뜀")
    args = ap.parse_args()
    if args.scheduled and (reason := should_skip_scheduled()):
        print(reason)
        return
    load_dotenv(Path(__file__).parent / ".env")

    bus = EventBus()
    if args.verbose:
        bus.subscribe(lambda e: print(f"[{e['name']}] {e['msg']}"))
    result = execute(bus, send=not args.dry_run, days=args.days, top=args.top, weekly=args.weekly or None)
    print(result["text"])
    if result["error"]:
        sys.exit(result["error"])


if __name__ == "__main__":
    main()

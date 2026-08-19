"""CLI 진입점.

    python -m avocado_ai.main --check                  # DB 붙는지 + 데이터 있는지만 확인
    python -m avocado_ai.main --sample                 # DB 없이 9종 유형 샘플로 생성만
    python -m avocado_ai.main --child-id 1 --dry-run   # 한 명분 생성 (DB 안 건드림)
    python -m avocado_ai.main                          # 지난달 전체 순회 후 UPDATE
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import replace
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from . import config as config_module
from . import db, repository
from .generator import AdviceGenerationError, build_client, generate
from .prompt import build_user_prompt, suggestion_direction

SEOUL = ZoneInfo("Asia/Seoul")

log = logging.getLogger("avocado_ai")


def previous_month_in_seoul() -> tuple[int, int]:
    """기본 대상은 '지난달'. 배치가 매월 1일에 도는 걸 전제로 한다."""
    now = datetime.now(SEOUL)
    return repository.previous_year_month(now.year, now.month)


# ── --sample 용 가짜 입력 ──────────────────────────────────────────
# DB 없이 프롬프트와 생성 품질만 먼저 보고 싶을 때 쓴다.
_SAMPLE_ROWS: list[dict[str, Any]] = [
    {
        "id": 0, "type_code": "SAVING_DREAMER", "type_name": "꿈꾸는 꿈돌이",
        "total_spent": 18000, "transaction_count": 6, "total_saved": 30000,
        "allowance_received": 50000, "saving_rate": 60.00, "last_month_spent": 20000,
        "top_spots": [{"percentage": 40}, {"percentage": 35}, {"percentage": 25}],
    },
    {
        "id": 0, "type_code": "ZERO_SPENDING", "type_name": "겨울잠 소비",
        "total_spent": 0, "transaction_count": 0, "total_saved": 20000,
        "allowance_received": 30000, "saving_rate": 66.67, "last_month_spent": 15000,
        "top_spots": [],
    },
    {
        "id": 0, "type_code": "FREQUENT_SPARROW", "type_name": "방앗간 못 지나가는 참새",
        "total_spent": 46000, "transaction_count": 31, "total_saved": 4000,
        "allowance_received": 50000, "saving_rate": 8.00, "last_month_spent": 42000,
        "top_spots": [{"percentage": 38}, {"percentage": 32}, {"percentage": 30}],
    },
    {
        "id": 0, "type_code": "BIG_SPENDER", "type_name": "큰 거 한방",
        "total_spent": 48000, "transaction_count": 3, "total_saved": 2000,
        "allowance_received": 50000, "saving_rate": 4.00, "last_month_spent": 45000,
        "top_spots": [{"percentage": 60}, {"percentage": 25}, {"percentage": 15}],
    },
    {   # 증가 케이스
        "id": 0, "type_code": "ROLLER_COASTER", "type_name": "롤러코스터 소비",
        "total_spent": 40000, "transaction_count": 14, "total_saved": 5000,
        "allowance_received": 50000, "saving_rate": 10.00, "last_month_spent": 15000,
        "top_spots": [{"percentage": 45}, {"percentage": 30}, {"percentage": 25}],
    },
    {   # 비교 대상 없음 — 전월 소비 0원이면 무조건 이 유형이 된다 (ONBOARDING 7.1)
        "id": 0, "type_code": "ROLLER_COASTER", "type_name": "롤러코스터 소비",
        "total_spent": 22000, "transaction_count": 9, "total_saved": 8000,
        "allowance_received": 30000, "saving_rate": 26.67, "last_month_spent": None,
        "top_spots": [{"percentage": 50}, {"percentage": 30}, {"percentage": 20}],
    },
    {
        "id": 0, "type_code": "CAREFUL_OWL", "type_name": "생각하고 쓰는 부엉이",
        "total_spent": 25000, "transaction_count": 7, "total_saved": 15000,
        "allowance_received": 50000, "saving_rate": 30.00, "last_month_spent": 28000,
        "top_spots": [{"percentage": 44}, {"percentage": 33}, {"percentage": 23}],
    },
    {
        "id": 0, "type_code": "ONE_STORE_SNIPER", "type_name": "하나만 노리는 저격수",
        "total_spent": 36000, "transaction_count": 18, "total_saved": 6000,
        "allowance_received": 50000, "saving_rate": 12.00, "last_month_spent": 33000,
        "top_spots": [{"percentage": 62}, {"percentage": 22}, {"percentage": 16}],
    },
    {
        "id": 0, "type_code": "SMALL_SAVER", "type_name": "티끌모아 부자",
        "total_spent": 8000, "transaction_count": 5, "total_saved": 22000,
        "allowance_received": 30000, "saving_rate": 73.33, "last_month_spent": 9000,
        "top_spots": [{"percentage": 50}, {"percentage": 30}, {"percentage": 20}],
    },
    {
        "id": 0, "type_code": "SPROUT", "type_name": "새싹형",
        "total_spent": 31000, "transaction_count": 13, "total_saved": 9000,
        "allowance_received": 50000, "saving_rate": 18.00, "last_month_spent": 29000,
        "top_spots": [{"percentage": 41}, {"percentage": 34}, {"percentage": 25}],
    },
]


def _print_advice(row: dict[str, Any], advice: Any) -> None:
    print(f"  제안 방향 : {suggestion_direction(row)}")
    print(f"  아이용({len(advice.child_advice):>2}자) : {advice.child_advice}")
    print(f"  보호자용({len(advice.parent_advice):>2}자) : {advice.parent_advice}")
    if advice.attempts > 1:
        print(f"  (재시도 {advice.attempts}회)")
    for w in advice.warnings:
        print(f"  ! {w}")


# ── 명령별 동작 ────────────────────────────────────────────────────

def cmd_check(cfg: config_module.Config) -> int:
    print(f"접속 시도: {cfg.db.user}@{cfg.db.host}:{cfg.db.port}/{cfg.db.name}")
    try:
        with db.connect(cfg.db) as conn:
            info = repository.overview(conn)
    except Exception as exc:
        print(f"\n[실패] {type(exc).__name__}: {exc}", file=sys.stderr)
        print(
            "\n대부분 DB 가 안 떠 있는 경우다. 백엔드 레포에서:\n"
            "    docker compose up -d mysql\n",
            file=sys.stderr,
        )
        return 1

    server = info["server"]
    print(f"[성공] MySQL {server['v']} / 서버시각 {server['now']} / time_zone {server['tz']}")
    print(f"  소비 유형 마스터 : {info['type_rows']}행 (9행이어야 정상)")
    print(f"  ACTIVE 지갑      : {info['active_wallets']}개")

    if not info["months"]:
        print("\n  리포트 데이터가 하나도 없다. 백엔드 배치가 아직 안 돌았다는 뜻이다.")
        return 0

    print("\n  월별 리포트 현황:")
    print("    연월      건수   child_advice NULL   parent_advice NULL")
    for m in info["months"]:
        ym = f"{m['report_year']}-{m['report_month']:02d}"
        print(
            f"    {ym}  {m['reports']:>5}   {int(m['child_advice_null'] or 0):>17}"
            f"   {int(m['parent_advice_null'] or 0):>18}"
        )

    year, month = previous_month_in_seoul()
    print(f"\n  기본 대상(지난달) = {year}-{month:02d}")
    return 0


def cmd_sample(cfg: config_module.Config, show_prompt: bool) -> int:
    client = build_client(cfg.openai)
    print(f"모델: {cfg.openai.model} — DB 없이 샘플 {len(_SAMPLE_ROWS)}건 생성\n")

    for row in _SAMPLE_ROWS:
        row = {**row, "report_year": 2026, "report_month": 7}
        label = row["type_code"]
        if row["type_code"] == "ROLLER_COASTER":
            label += " (비교 대상 없음)" if not row["last_month_spent"] else " (증가)"
        print(f"[{label}] {row['type_name']}")

        if show_prompt:
            print("--- user prompt ---")
            print(build_user_prompt(row, cfg.advice))
            print("-------------------")

        try:
            advice = generate(client, cfg.openai, cfg.advice, row)
        except AdviceGenerationError as exc:
            print(f"  [실패] {exc}\n")
            continue
        _print_advice(row, advice)
        print()
    return 0


def cmd_run(cfg: config_module.Config, args: argparse.Namespace) -> int:
    year, month = args.year, args.month
    if year is None or month is None:
        year, month = previous_month_in_seoul()

    with db.connect(cfg.db) as conn:
        targets = repository.find_targets(conn, year, month, args.child_id)
        if args.limit:
            targets = targets[: args.limit]

        mode = "DRY RUN — DB 안 건드림" if args.dry_run else "실제 UPDATE"
        print(f"대상 {year}-{month:02d} / {len(targets)}건 / 모델 {cfg.openai.model} / {mode}\n")
        if not targets:
            print("채울 행이 없다. --check 로 데이터 상태를 먼저 보라.")
            return 0

        client = build_client(cfg.openai)
        ok = failed = 0

        for row in targets:
            print(f"[report_id={row['id']}] {row['type_name']} ({row['type_code']})")
            try:
                advice = generate(client, cfg.openai, cfg.advice, row)
            except AdviceGenerationError as exc:
                # 실패한 행은 NULL 로 남긴다. 다음 실행 때 다시 대상이 된다.
                print(f"  [실패] {exc} — 컬럼은 NULL 로 남긴다\n")
                failed += 1
                continue

            _print_advice(row, advice)
            if not args.dry_run:
                repository.update_advice(conn, row["id"], advice.child_advice, advice.parent_advice)
                conn.commit()
                print("  → UPDATE 완료")
            ok += 1
            print()

        print(f"완료: 성공 {ok}건 / 실패 {failed}건")
    return 0 if failed == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="avocado-ai",
        description="월간 소비 리포트에 AI 조언(아이용/보호자용)을 채워 넣는다.",
    )
    parser.add_argument("--check", action="store_true", help="DB 접속과 데이터 상태만 확인하고 끝낸다")
    parser.add_argument("--sample", action="store_true", help="DB 없이 9종 유형 샘플로 생성만 해본다")
    parser.add_argument("--show-prompt", action="store_true", help="--sample 과 함께: 실제 프롬프트도 출력")
    parser.add_argument("--year", type=int, help="대상 연도 (기본: 지난달)")
    parser.add_argument("--month", type=int, help="대상 월 (기본: 지난달)")
    parser.add_argument("--child-id", type=int, help="특정 아이 한 명만 처리")
    parser.add_argument("--limit", type=int, help="앞에서 N건만 처리")
    parser.add_argument("--dry-run", action="store_true", help="생성만 하고 UPDATE 하지 않는다")
    parser.add_argument(
        "--model",
        help="OPENAI_MODEL 을 무시하고 이 모델로 돈다 (예: gpt-5-nano, gpt-4o-mini)",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    cfg = config_module.load()
    if args.model:
        cfg = replace(cfg, openai=replace(cfg.openai, model=args.model))

    if args.check:
        return cmd_check(cfg)
    if args.sample:
        return cmd_sample(cfg, args.show_prompt)
    if (args.year is None) != (args.month is None):
        parser.error("--year 와 --month 는 같이 준다")
    return cmd_run(cfg, args)


if __name__ == "__main__":
    raise SystemExit(main())

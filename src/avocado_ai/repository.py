"""child_spending_reports 조회 / advice UPDATE (ONBOARDING 6절)."""

from __future__ import annotations

import json
from typing import Any

import pymysql

# 대상 조회. 전월 행을 LEFT JOIN 해서 last_month_spent 를 같이 가져온다.
# ROLLER_COASTER 예외 처리에만 쓴다 (ONBOARDING 7.1).
_SELECT_TARGETS = """
SELECT r.id, r.child_id, r.report_year, r.report_month,
       r.total_spent, r.transaction_count, r.top_spots,
       r.total_saved, r.allowance_received, r.saving_rate,
       r.child_advice, r.parent_advice,
       t.code AS type_code, t.name AS type_name,
       p.total_spent AS last_month_spent
FROM child_spending_reports r
JOIN spending_report_types t ON t.id = r.report_type_id
LEFT JOIN child_spending_reports p
       ON p.child_id     = r.child_id
      AND p.report_year  = %(prev_year)s
      AND p.report_month = %(prev_month)s
WHERE r.report_year = %(year)s AND r.report_month = %(month)s
  AND (r.child_advice IS NULL OR r.parent_advice IS NULL)
"""

# --force 용. 이미 채워진 행까지 포함한다.
_SELECT_TARGETS_ALL = _SELECT_TARGETS.replace(
    "  AND (r.child_advice IS NULL OR r.parent_advice IS NULL)\n", ""
)

_UPDATE_ADVICE = """
UPDATE child_spending_reports
SET child_advice = %(child_advice)s, parent_advice = %(parent_advice)s
WHERE id = %(id)s
"""


def previous_year_month(year: int, month: int) -> tuple[int, int]:
    """전월 연/월. 1월이면 전년 12월. SQL 에서 -1 하면 0월이 되므로 여기서 계산한다."""
    if month == 1:
        return year - 1, 12
    return year, month - 1


def find_targets(
    conn: pymysql.connections.Connection,
    year: int,
    month: int,
    child_id: int | None = None,
    include_done: bool = False,
) -> list[dict[str, Any]]:
    """조언이 아직 안 채워진 행을 가져온다. child_id 를 주면 그 아이만.

    include_done=True 면 이미 채워진 행까지 포함한다. 시연 데이터를 만들거나
    프롬프트를 고쳐가며 다시 생성할 때 쓴다. 평소 배치에서는 쓰지 않는다.
    """
    prev_year, prev_month = previous_year_month(year, month)
    sql = _SELECT_TARGETS_ALL if include_done else _SELECT_TARGETS
    params: dict[str, Any] = {
        "year": year,
        "month": month,
        "prev_year": prev_year,
        "prev_month": prev_month,
    }
    if child_id is not None:
        sql += " AND r.child_id = %(child_id)s"
        params["child_id"] = child_id
    sql += " ORDER BY r.id"

    with conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()

    for row in rows:
        row["top_spots"] = _parse_top_spots(row.get("top_spots"))
    return rows


def _parse_top_spots(raw: Any) -> list[dict[str, Any]]:
    if not raw:
        return []
    if isinstance(raw, (list, tuple)):
        return list(raw)
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8")
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return []
    return parsed if isinstance(parsed, list) else []


def update_advice(
    conn: pymysql.connections.Connection,
    report_id: int,
    child_advice: str | None,
    parent_advice: str | None,
) -> int:
    with conn.cursor() as cur:
        return cur.execute(
            _UPDATE_ADVICE,
            {"id": report_id, "child_advice": child_advice, "parent_advice": parent_advice},
        )


def overview(conn: pymysql.connections.Connection) -> dict[str, Any]:
    """--check 용. DB 가 살아 있는지 + 리포트 데이터가 있는지 한 번에 본다."""
    out: dict[str, Any] = {}
    with conn.cursor() as cur:
        cur.execute("SELECT VERSION() AS v, NOW() AS now, @@time_zone AS tz")
        out["server"] = cur.fetchone()

        cur.execute("SELECT COUNT(*) AS c FROM spending_report_types")
        out["type_rows"] = cur.fetchone()["c"]

        cur.execute("SELECT COUNT(*) AS c FROM wallets WHERE status = 'ACTIVE'")
        out["active_wallets"] = cur.fetchone()["c"]

        cur.execute(
            """
            SELECT report_year, report_month,
                   COUNT(*)                     AS reports,
                   SUM(child_advice  IS NULL)   AS child_advice_null,
                   SUM(parent_advice IS NULL)   AS parent_advice_null
            FROM child_spending_reports
            GROUP BY report_year, report_month
            ORDER BY report_year, report_month
            """
        )
        out["months"] = list(cur.fetchall())
    return out

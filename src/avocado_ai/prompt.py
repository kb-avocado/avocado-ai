"""프롬프트 구성

핵심 두 가지만 기억하면 된다.
1. 아이용은 만 6세 눈높이, 보호자용은 성인 눈높이 — 기준이 다르다.
2. 조언은 "관찰 한 문장 + 제안 한 문장". 제안 없이 설명만 있으면 조언이 아니다.
"""

from __future__ import annotations

from typing import Any

from .config import AdviceConfig

# 유형별 판정 기준. 평소에는 DB 의 spending_report_types.description 을 그대로 쓴다
# (report_type_id FK 조인으로 행마다 따라온다). 아래 상수는 --sample 처럼
# DB 없이 도는 경우의 폴백일 뿐이다. 내용은 DB 값과 같다.
_TYPE_CRITERIA_FALLBACK: dict[str, str] = {
    "SAVING_DREAMER": "그 달 저금통 목표를 2개 이상 달성",
    "ZERO_SPENDING": "그 달 소비가 0원",
    "FREQUENT_SPARROW": "소비한 날짜가 25일 이상",
    "BIG_SPENDER": "평균 결제액 15,000원 이상이면서 결제 5건 이하",
    "ROLLER_COASTER": "전월 대비 증감률 절대값 50% 이상",
    "CAREFUL_OWL": "결제 10건 이하",
    "ONE_STORE_SNIPER": "한 가맹점 결제 지분 50% 이상",
    "SMALL_SAVER": "총 소비 10,000원 이하",
    "SPROUT": "위 어디에도 걸리지 않는 기본값",
}

# 유형별 제안 방향 (ONBOARDING 7절 표). 만 6세가 할 수 있는 행동으로 맞춰져 있다.
# 월 단위 → 주/일 단위, 금액 기준 → 횟수 기준, 추상적 규칙 → 눈에 보이는 행동.
SUGGESTION_DIRECTION: dict[str, str] = {
    "SAVING_DREAMER": "다음에 모을 것을 아이가 직접 고르게 하기",
    "ZERO_SPENDING": "모아둔 용돈으로 갖고 싶은 것 하나를 말해보게 하기",
    "FREQUENT_SPARROW": "요일 하나를 정해 그날은 쓰지 않기 (달력에 표시하면 더 좋다)",
    "BIG_SPENDER": "갖고 싶은 걸 종이에 적어두고 다음에 다시 보기",
    "CAREFUL_OWL": "무엇을 참았는지 물어보고 그 판단을 인정해주기",
    "ONE_STORE_SNIPER": "그 가게에 일주일에 몇 번 갈지 함께 정하기",
    "SMALL_SAVER": "아낀 돈으로 하고 싶은 것 하나를 함께 정하기",
    "SPROUT": "다음 달에 해볼 약속 하나를 아이가 고르게 하기",
    # ROLLER_COASTER 는 증감 방향에 따라 갈리므로 아래 함수에서 따로 만든다.
}

_ROLLER_COASTER_UP = "이번 달에 무엇을 샀는지 하나만 떠올려보게 하기"
_ROLLER_COASTER_DOWN = "지난달보다 아낀 점을 구체적으로 칭찬해주기"
_ROLLER_COASTER_NO_BASE = "이번 달이 첫 기록이라는 점을 알려주고, 다음 달에 해볼 약속 하나 정하기"


def build_system_prompt(cfg: AdviceConfig) -> str:
    return f"""너는 아이 용돈 관리 앱 '아보카도'의 마스코트 "아보카도 씨"다.
한 달 소비 리포트를 보고 조언 두 개를 쓴다. 하나는 아이가 읽고, 하나는 보호자가 읽는다.

## 읽는 사람이 다르다

- childAdvice — **만 6세 아이도 읽는다.** 서비스 사용자는 만 6~13세지만 눈높이는 가장 낮은 쪽에 맞춘다.
- parentAdvice — **보호자(성인)가 읽는다.** 어휘 제약 없음. 다만 제안하는 행동은 아이가 할 수 있어야 한다.

## 문장 구조 — 관찰 + 제안

두 조언 모두 **사실 한 문장 + 행동 제안 한 문장**으로 쓴다.
설명만 하고 끝내지 마라. 읽고 나서 뭘 할지 알 수 있어야 조언이다.

- childAdvice: 잘한 점을 짚어 인정 → 다음 달에 **아이가** 해볼 것 하나
- parentAdvice: 집계값에서 나온 사실 → **보호자가 아이와 함께** 해볼 것 하나

제안은 **하나만** 넣는다. 두 개를 넣으면 둘 다 뭉개진다.

## 가게 이름

"많이 쓴 곳"에 가게 이름이 주어지면 조언에 **그대로 써도 된다.** "그 가게"보다 구체적이라 잘 읽힌다.
이름에서 어떤 종류의 가게인지 분명하면 그렇게 불러도 된다 (예: '아보편의점' → "편의점").
**단, 확실하지 않으면 추측하지 마라.** 주어진 이름만 쓰고 없는 업종을 지어내지 마라.

## 아이용 어휘 규칙 (childAdvice 에만 적용)

- 한자어·금융 용어를 일상어로: 지출/소비 → "쓴 돈", 저축률 → "모은 비율",
  소비 패턴 → "돈 쓰는 습관", 예산 → "미리 정한 돈"
- 한 문장을 짧게 끊는다
- 금액은 만 원 단위로 뭉뚱그린다 ("12,340원" 대신 "만 원쯤")
- 비율은 백분율보다 "절반", "열 번 중 세 번" 같은 말로
- 다정한 존댓말

parentAdvice 에는 이 규칙을 적용하지 마라. 성인에게 "쓴 돈"이라고 하면 어색하다.

## 길이

각각 **한국어 {cfg.min_len}~{cfg.soft_max_len}자**를 지킨다. **{cfg.max_len}자를 절대 넘기지 마라.**
고정 높이 칠판 UI에 들어가서 넘치면 배경이 깨진다.

## 금지

- 아이를 나무라거나 부끄럽게 하는 표현
- 금액 목표를 강요하는 표현 ("다음 달엔 3만 원은 모아야 해요")
- 특정 가게에서 더 쓰라고 부추기는 표현
- 이모지 남용 (안 쓰는 쪽이 기본)
- 주어진 판정 기준 문장을 그대로 되풀이하기 — 그건 "왜 이 유형인지"라 조언이 아니다

## 출력

JSON 하나로만 답한다: {{"childAdvice": "...", "parentAdvice": "..."}}"""


# Structured Outputs 용 스키마. 길이는 스키마로 강제되지 않으므로 코드에서 따로 검사한다.
RESPONSE_SCHEMA: dict[str, Any] = {
    "name": "spending_advice",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "childAdvice": {
                "type": "string",
                "description": "아이(만 6세 눈높이)가 읽을 조언. 관찰 한 문장 + 제안 한 문장.",
            },
            "parentAdvice": {
                "type": "string",
                "description": "보호자(성인)가 읽을 조언. 사실 한 문장 + 함께 할 행동 제안 한 문장.",
            },
        },
        "required": ["childAdvice", "parentAdvice"],
        "additionalProperties": False,
    },
}


def type_criteria(row: dict[str, Any]) -> str:
    """이 행이 왜 그 유형이 됐는지. DB 값을 우선 쓰고 없으면 폴백."""
    from_db = (row.get("type_description") or "").strip()
    if from_db:
        return from_db
    return _TYPE_CRITERIA_FALLBACK.get(row.get("type_code"), "기본값")


def suggestion_direction(row: dict[str, Any]) -> str:
    """유형별 제안 방향. ROLLER_COASTER 만 전월 값에 따라 갈린다 (ONBOARDING 7.1)."""
    code = row.get("type_code")
    if code != "ROLLER_COASTER":
        return SUGGESTION_DIRECTION.get(code, SUGGESTION_DIRECTION["SPROUT"])

    last = row.get("last_month_spent")
    if not last:  # NULL 또는 0 — 비교할 지난달이 없다
        return _ROLLER_COASTER_NO_BASE
    return _ROLLER_COASTER_UP if (row.get("total_spent") or 0) > last else _ROLLER_COASTER_DOWN


def _won(amount: Any) -> str:
    return f"{int(amount or 0):,}원"


def _top_spots_lines(row: dict[str, Any], cfg: AdviceConfig) -> list[str]:
    """상위 3개만 쓴다. 백엔드가 TOP 5 를 넣어두므로 여기서 자른다 (ONBOARDING 4.1).

    JSON 필드 이름이 category 지만 **실제로 담긴 값은 상호명**이다 (백엔드가 m.name 을
    category 라는 별칭으로 넣는다). merchants 테이블에 업종 컬럼이 따로 있긴 한데
    정식 데이터가 아닌 목업이라 쓰지 않는다.
    """
    spots = (row.get("top_spots") or [])[:3]
    if not spots:
        return ["- 많이 쓴 곳: 기록 없음"]

    lines = ["- 많이 쓴 곳 (상위 3):"]
    for i, spot in enumerate(spots, start=1):
        share = spot.get("percentage")
        share_text = f"전체의 {share}%" if share is not None else "비율 미상"
        amount = spot.get("amount")
        amount_text = f", {_won(amount)}" if amount is not None else ""

        if cfg.include_merchant_names:
            label = spot.get("category") or spot.get("merchant_name") or "기타"
        else:
            label = f"{i}번째로 많이 간 곳"
        lines.append(f"    {i}위 {label} — {share_text}{amount_text}")
    return lines


def _roller_coaster_lines(row: dict[str, Any]) -> list[str]:
    """ROLLER_COASTER 는 전월 값을 반드시 같이 준다.

    전월 소비가 0원이면 백엔드가 무조건 이 유형으로 확정해버리기 때문에,
    비교 대상이 없다는 사실을 명시하지 않으면 모델이 없는 증감을 지어낸다.
    """
    if row.get("type_code") != "ROLLER_COASTER":
        return []

    last = row.get("last_month_spent")
    if not last:
        return [
            "",
            "[전월 대비]",
            "- 비교할 지난달 기록이 없다 (이번 달이 첫 기록).",
            "- **늘었다/줄었다 같은 증감 표현을 절대 쓰지 마라.**",
        ]

    total = int(row.get("total_spent") or 0)
    direction = "늘었다" if total > last else "줄었다"
    return [
        "",
        "[전월 대비]",
        f"- 지난달 {_won(last)} → 이번 달 {_won(total)} ({direction})",
        f"- 증감 방향은 '{direction}'로 고정. 반대로 쓰지 마라.",
    ]


def build_user_prompt(row: dict[str, Any], cfg: AdviceConfig) -> str:
    """집계값만 넣는다. 아이 실명·생년월일·child_id 는 넣지 않는다 (ONBOARDING 7절)."""
    code = row.get("type_code") or "SPROUT"
    lines = [
        f"[{row['report_year']}년 {row['report_month']}월 집계]",
        f"- 쓴 돈 총액: {_won(row.get('total_spent'))}",
        f"- 결제 건수: {int(row.get('transaction_count') or 0)}건",
        f"- 저금한 돈: {_won(row.get('total_saved'))}",
        f"- 받은 용돈: {_won(row.get('allowance_received'))}",
        f"- 저축률: {row.get('saving_rate')}%",
        *_top_spots_lines(row, cfg),
        "",
        "[소비 유형]",
        f"- {row.get('type_name')} ({code})",
        f"- 이 유형이 된 이유: {type_criteria(row)}",
        "  (이 문장은 맥락일 뿐이다. 조언에 그대로 옮겨 쓰지 마라.)",
        *_roller_coaster_lines(row),
        "",
        "[이번 조언의 제안 방향]",
        f"- {suggestion_direction(row)}",
        "",
        "위 방향을 지키되 문장은 네가 자연스럽게 쓴다.",
        "childAdvice 와 parentAdvice 를 각각 만들어 JSON 으로만 답하라.",
    ]
    return "\n".join(lines)

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
    "SAVING_DREAMER": "목표 달성 축하해준다. 저축을 잘했다는 사실에서 끝내지 말고, 모은 돈과 앞으로의 목표를 연결한다.",
    "ZERO_SPENDING": "앱 방문 유도(출석체크) 및 소비/저축의 가치 전달, 돈을 쓰지 않는 것 자체가 목표가 되지 않도록 한다.",
    "FREQUENT_SPARROW": "자주 쓴다는 사실보다, 자주 쓰면서 실제로 얼마를 썼는지 돌아보게 한다. + 지출 TOP 3 장소 인지 및 지출 통제 챌린지",
    "BIG_SPENDER": "지출 TOP 3 분석을 통한 큰 지출의 패턴 파악 및 구매 전 저금통 기능을 활용해 '생각 시간' 가질 수 있도록 유도",
    "CAREFUL_OWL": "올바른 소비 습관 칭찬 + 시드머니를 통한 이자/금융 개념 교육, 확장",
    "ONE_STORE_SNIPER": "지출 TOP 3 데이터를 통한 몰입성 소비 인지, (다른 카테고리로의 소비 경험 확장)",
    "SMALL_SAVER": "알뜰하게 남긴 멋진 용돈, 이번 달엔 어떻게 해볼까? 차곡차곡 모으기/나를 위한 선물(소소한 보상 소비) 제안",
    "SPROUT": "유형 지정 대신 '이번 달 리포트 데이터' 요약 제공을 통해 자신의 스타일 탐색 유도",
    # ROLLER_COASTER 는 증감 방향에 따라 갈리므로 아래 함수에서 따로 만든다.
}

_ROLLER_COASTER_UP = "지출 균형 맞추기 및 정기 예산/저금통 활용, 왜 늘었는지 돌아보도록 유도"
_ROLLER_COASTER_DOWN = "지출 균형 맞추기 및 정기 예산/저금통 활용, 칭찬, 왜 줄었는지 돌아보도록 유도"



def build_system_prompt(cfg: AdviceConfig) -> str:
    return f"""
너는 보호자 함께하는 어린이 금융습관 형성 전자지갑 웹앱 '아보카도'의 마스코트 "아보카도 씨"다.
한 달 소비 리포트를 보고 조언 두 개를 쓴다.
하나는 아이가 읽고(childAdvice), 하나는 보호자가 읽는다(parentAdvice).
서비스 사용자는 만 6~13세지만, childAdvice 의 눈높이는 초등학교 저학년에 해당하는 **만 6세~8세**에 맞춘다.

## 1. 조언의 형태 — 관찰 + 제안

두 조언 모두 **사실 한 문장 + 행동 제안 한 문장**으로 쓴다.
설명만 하고 끝내지 마라. 읽고 나서 뭘 할지 알 수 있어야 조언이다.

- childAdvice: 잘한 점을 짚어 인정 → 다음 달에 아이가 해볼 것 하나
- parentAdvice: 집계값에서 나온 사실 → 보호자가 아이와 함께 해볼 것 하나

제안은 하나만 넣는다. 두 개를 넣으면 둘 다 뭉개진다.

## 2. 주어진 데이터를 다루는 법

- "많이 쓴 곳"에 가게 이름이 주어지면 조언에 그대로 써도 된다. "그 가게"보다 구체적이라 잘 읽힌다.
  이름에서 어떤 종류의 가게인지 분명하면 그렇게 불러도 된다 (예: '아보편의점' → "편의점").
  **단, 확실하지 않으면 추측하지 마라.** 주어진 이름만 쓰고 없는 업종을 지어내지 마라.
- 유형 판정 기준 문장을 **그대로 되풀이하지 마라.** 그건 "왜 이 유형인지"라 조언이 아니다.
  방향만 참고하고, 조언에 담을 내용은 집계값에서 끌어낸다.

## 3. 말투와 어휘

두 조언 모두 문장을 **해요체**(~예요, ~했어요, ~보세요)로 끝낸다.
하십시오체(~습니다)나 반말(~야, ~다)을 섞지 마라. 한 조언 안에서도 끝까지 통일한다.
금액은 한국 원화(KRW)로만 쓴다. 단위는 **"원"** 이다. 다른 화폐로 환산하거나 "$", "won" 같은 표기를 쓰지 마라.

childAdvice — 만 6세~8세가 읽는다:

- 한자어·금융 용어를 일상어로: 지출/소비 → "쓴 돈", 소비 패턴 → "돈 쓰는 습관", 예산 → "미리 정한 돈"
- 한 문장을 짧게 끊는다
- 비율은 백분율보다 "절반", "열 번 중 세 번" 같은 말로
- 다정한 말씨

parentAdvice — 보호자(성인)가 읽는다. 위 childAdvice의 어휘 규칙을 적용하지 마라. 성인에게 "쓴 돈"이라고 하면 어색하다.
어휘 제약은 없지만, 제안하는 행동은 아이가 할 수 있어야 한다.

## 4. 금지

- 아이를 나무라거나 부끄럽게 하는 표현
- 금액 목표를 강요하는 표현 ("다음 달엔 3만 원은 모아야 해요")
- 특정 가게에서 더 쓰라고 부추기는 표현
- 이모지 남용 (안 쓰는 쪽이 기본)

## 5. 출력

- 길이는 각각 한국어 {cfg.min_len}~{cfg.soft_max_len}자를 지킨다. **{cfg.max_len}자를 절대 넘기지 마라.**
  고정 높이 칠판 UI에 들어가서 넘치면 배경이 깨진다.
- **JSON 하나로만 답한다:** {{"childAdvice": "...", "parentAdvice": "..."}}"""


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
        f"- 한 달간 쓴 돈 총액: {_won(row.get('total_spent'))}",
        f"- 결제 건수: {int(row.get('transaction_count') or 0)}건",
        f"- 저금한 돈: {_won(row.get('total_saved'))}",
        f"- 받은 용돈: {_won(row.get('allowance_received'))}",
        f"- 저축률: {row.get('saving_rate')}%",
        *_top_spots_lines(row, cfg),
        "",
        "[소비 유형]",
        f"- {row.get('type_name')} ({code})",
        f"- 이 유형이 된 이유: {type_criteria(row)}",
        "  (이 문장은 맥락일 뿐이다. 조언에 그대로 옮겨 쓰지 마라. 방향만 참고하되 조언 자체는 집계값을 위주로 생성해라.)",
        *_roller_coaster_lines(row),
        "",
        "[이번 조언의 제안 방향]",
        f"- {suggestion_direction(row)}",
        "",
        "위 방향을 지키되 문장은 네가 자연스럽게 쓴다.",
        "childAdvice 와 parentAdvice 를 각각 만들어 JSON 으로만 답하라.",
    ]
    return "\n".join(lines)

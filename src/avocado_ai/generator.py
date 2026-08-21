"""OpenAI 호출 + 결과 검증.

Structured Outputs 로 JSON 파싱 실패는 막을 수 있지만 **길이는 스키마로 강제되지 않는다.**
그래서 길이는 여기서 직접 재고, 넘치면 그 사실을 알려주며 재생성시킨다.
끝내 못 맞추면 None 을 돌려주고 호출부가 컬럼을 NULL 로 남긴다 (ONBOARDING 7절).
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from openai import OpenAI

from .config import AdviceConfig, OpenAiConfig
from .prompt import RESPONSE_SCHEMA, build_system_prompt, build_user_prompt

log = logging.getLogger(__name__)


@dataclass
class Usage:
    """토큰 사용량. 재시도한 시도까지 전부 합산한다 — 실패한 호출도 과금되기 때문이다."""

    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0  # 추론 모델이 output 안에서 따로 쓴 몫
    cached_tokens: int = 0  # 입력 중 캐시로 처리돼 할인되는 몫

    def add_response(self, response: Any) -> None:
        u = getattr(response, "usage", None)
        if u is None:
            return
        self.calls += 1
        self.input_tokens += getattr(u, "prompt_tokens", 0) or 0
        self.output_tokens += getattr(u, "completion_tokens", 0) or 0

        detail = getattr(u, "completion_tokens_details", None)
        if detail is not None:
            self.reasoning_tokens += getattr(detail, "reasoning_tokens", 0) or 0
        detail = getattr(u, "prompt_tokens_details", None)
        if detail is not None:
            self.cached_tokens += getattr(detail, "cached_tokens", 0) or 0

    def merge(self, other: Usage) -> None:
        self.calls += other.calls
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.reasoning_tokens += other.reasoning_tokens
        self.cached_tokens += other.cached_tokens

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def summary(self) -> str:
        parts = [f"입력 {self.input_tokens:,}", f"출력 {self.output_tokens:,}"]
        if self.reasoning_tokens:
            parts.append(f"추론 {self.reasoning_tokens:,}")
        if self.cached_tokens:
            parts.append(f"캐시 {self.cached_tokens:,}")
        return f"{' / '.join(parts)}  합계 {self.total_tokens:,} 토큰  (호출 {self.calls}회)"


@dataclass
class Advice:
    child_advice: str
    parent_advice: str
    attempts: int = 1
    warnings: list[str] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)


class AdviceGenerationError(Exception):
    """재시도를 다 쓰고도 규격을 못 맞춘 경우.

    끝내 실패했어도 호출한 만큼은 과금되므로 사용량을 함께 들고 나간다.
    """

    def __init__(self, message: str, usage: Usage | None = None) -> None:
        super().__init__(message)
        self.usage = usage or Usage()


def build_client(cfg: OpenAiConfig) -> OpenAI:
    if not cfg.api_key:
        raise RuntimeError("OPENAI_API_KEY 가 비어 있다. .env 를 확인할 것.")
    return OpenAI(api_key=cfg.api_key)


def _too_long(text: str, limit: int) -> bool:
    return len(text) > limit


def _check(advice: dict[str, str], cfg: AdviceConfig) -> tuple[list[str], list[str]]:
    """(치명적 문제, 경고) 를 나눠 돌려준다. 치명적 문제가 있으면 재생성한다."""
    errors: list[str] = []
    warnings: list[str] = []

    for key, label in (("childAdvice", "아이용"), ("parentAdvice", "보호자용")):
        text = (advice.get(key) or "").strip()
        length = len(text)

        if not text:
            errors.append(f"{label} 조언이 비어 있다.")
            continue
        if _too_long(text, cfg.max_len):
            errors.append(
                f"{label} 조언이 {length}자로 최대 {cfg.max_len}자를 넘었다. 더 짧게 다시 써라."
            )
            continue
        if length > cfg.soft_max_len:
            warnings.append(f"{label} {length}자 (권장 {cfg.soft_max_len}자 초과)")
        elif length < cfg.min_len:
            warnings.append(f"{label} {length}자 (권장 {cfg.min_len}자 미만)")

    return errors, warnings


def generate(
    client: OpenAI,
    openai_cfg: OpenAiConfig,
    advice_cfg: AdviceConfig,
    row: dict[str, Any],
) -> Advice:
    system_prompt = build_system_prompt(advice_cfg)
    user_prompt = build_user_prompt(row, advice_cfg)

    messages: list[dict[str, str]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    last_problem = "원인 미상"
    usage = Usage()

    for attempt in range(1, openai_cfg.max_retries + 1):
        try:
            response = client.chat.completions.create(
                model=openai_cfg.model,
                messages=messages,
                response_format={"type": "json_schema", "json_schema": RESPONSE_SCHEMA},
            )
            usage.add_response(response)
            raw = response.choices[0].message.content or "{}"
            parsed = json.loads(raw)
        except Exception as exc:  # API 오류 / 네트워크 / 파싱
            last_problem = f"{type(exc).__name__}: {exc}"
            log.warning("report_id=%s 시도 %d 실패 — %s", row.get("id"), attempt, last_problem)
            if attempt < openai_cfg.max_retries:
                time.sleep(2**attempt)
            continue

        errors, warnings = _check(parsed, advice_cfg)
        if not errors:
            return Advice(
                child_advice=parsed["childAdvice"].strip(),
                parent_advice=parsed["parentAdvice"].strip(),
                attempts=attempt,
                warnings=warnings,
                usage=usage,
            )

        last_problem = " / ".join(errors)
        log.warning("report_id=%s 시도 %d 규격 미달 — %s", row.get("id"), attempt, last_problem)

        # 뭘 틀렸는지 알려주고 같은 대화에서 다시 쓰게 한다
        messages.append({"role": "assistant", "content": raw})
        messages.append(
            {
                "role": "user",
                "content": "다음 문제가 있다. 고쳐서 다시 써라.\n"
                + "\n".join(f"- {e}" for e in errors),
            }
        )

    raise AdviceGenerationError(last_problem, usage)

"""환경변수 로딩. .env 를 읽어 설정 객체 하나로 묶는다."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _int(name: str, default: int) -> int:
    raw = os.getenv(name)
    return int(raw) if raw else default


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class DbConfig:
    host: str
    port: int
    user: str
    password: str
    name: str


@dataclass(frozen=True)
class OpenAiConfig:
    api_key: str
    model: str
    max_retries: int


@dataclass(frozen=True)
class AdviceConfig:
    max_len: int
    min_len: int
    soft_max_len: int
    include_merchant_names: bool


@dataclass(frozen=True)
class Config:
    db: DbConfig
    openai: OpenAiConfig
    advice: AdviceConfig


def load() -> Config:
    return Config(
        db=DbConfig(
            host=os.getenv("DB_HOST", "127.0.0.1"),
            port=_int("DB_PORT", 3307),
            user=os.getenv("DB_USER", "avocado"),
            password=os.getenv("DB_PASSWORD", ""),
            name=os.getenv("DB_NAME", "avocado"),
        ),
        openai=OpenAiConfig(
            api_key=os.getenv("OPENAI_API_KEY", ""),
            model=os.getenv("OPENAI_MODEL", "gpt-5-nano"),
            max_retries=_int("OPENAI_MAX_RETRIES", 3),
        ),
        advice=AdviceConfig(
            max_len=_int("ADVICE_MAX_LEN", 90),
            min_len=_int("ADVICE_MIN_LEN", 30),
            soft_max_len=_int("ADVICE_SOFT_MAX_LEN", 70),
            include_merchant_names=_bool("INCLUDE_MERCHANT_NAMES", True),
        ),
    )

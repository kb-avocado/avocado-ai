"""MySQL 커넥션. utf8mb4 / Asia/Seoul 고정 (ONBOARDING 4.4)."""

from __future__ import annotations

import contextlib
from collections.abc import Iterator

import pymysql
from pymysql.cursors import DictCursor

from .config import DbConfig


@contextlib.contextmanager
def connect(cfg: DbConfig) -> Iterator[pymysql.connections.Connection]:
    conn = pymysql.connect(
        host=cfg.host,
        port=cfg.port,
        user=cfg.user,
        password=cfg.password,
        database=cfg.name,
        charset="utf8mb4",
        cursorclass=DictCursor,
        init_command="SET time_zone = '+09:00'",
        autocommit=False,
    )
    try:
        yield conn
    finally:
        conn.close()

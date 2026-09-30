"""A/B/C 공통 MySQL 접속 (접속 정보는 환경변수로만)"""

from __future__ import annotations

import os
import time
from collections.abc import Iterator
from contextlib import contextmanager

import pymysql
from pymysql.cursors import DictCursor

# 호출측이 드라이버를 직접 import하지 않도록 재노출
DatabaseError = pymysql.MySQLError
IntegrityError = pymysql.err.IntegrityError

_REQUIRED = ("DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD")
_CONNECT_TIMEOUT_SECONDS = 5

# DNS 조회 실패나 연결 끊김(2006/2013) 시 잠깐 쉬고 재시도
_TRANSIENT_ERROR_CODES = (2003, 2006, 2013)
_CONNECT_ATTEMPTS = 4
_RETRY_BASE_DELAY_SECONDS = 0.3


class DatabaseConfigError(RuntimeError):
    """DB 접속 환경변수 누락"""


def connection_settings() -> dict:
    """호출 시점의 환경변수로 접속 설정 구성"""

    missing = [key for key in _REQUIRED if os.environ.get(key) is None]
    if missing:
        raise DatabaseConfigError(
            f"DB 접속 정보가 없습니다: {', '.join(missing)} - .env 에 설정하세요."
        )

    settings = {
        "host": os.environ["DB_HOST"],
        "port": int(os.environ.get("DB_PORT", "3306")),
        "database": os.environ["DB_NAME"],
        "user": os.environ["DB_USER"],
        "password": os.environ["DB_PASSWORD"],
    }
    ssl_ca = os.environ.get("DB_SSL_CA")
    if ssl_ca:
        settings["ssl"] = {"ca": ssl_ca}
    return settings


def connect() -> pymysql.connections.Connection:
    settings = connection_settings()
    for attempt in range(_CONNECT_ATTEMPTS):
        try:
            return pymysql.connect(
                **settings,
                charset="utf8mb4",
                cursorclass=DictCursor,
                autocommit=False,
                connect_timeout=_CONNECT_TIMEOUT_SECONDS,
            )
        except pymysql.err.OperationalError as exc:
            code = exc.args[0] if exc.args else None
            if code not in _TRANSIENT_ERROR_CODES or attempt == _CONNECT_ATTEMPTS - 1:
                raise
            time.sleep(_RETRY_BASE_DELAY_SECONDS * 2**attempt)
    raise AssertionError("unreachable")  # pragma: no cover


@contextmanager
def transaction() -> Iterator[pymysql.cursors.DictCursor]:
    """커서 하나를 트랜잭션으로 감싸고 예외 시 롤백"""

    conn = connect()
    try:
        with conn.cursor() as cur:
            yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

"""LLM 하루 요청 수 제한과 토큰 사용량 기록 (MySQL, UTC 기준)"""

from __future__ import annotations

import logging
import threading
from datetime import date, datetime, timezone

from shared import database

from . import config

logger = logging.getLogger(__name__)

# 같은 프로세스 안의 동시 예약 경합 완화
_lock = threading.Lock()


def _today() -> date:
    return datetime.now(timezone.utc).date()


def try_reserve() -> bool:
    """요청 1회 예약, 상한 도달 또는 기록 실패 시 False"""

    limit = config.LLM_DAILY_REQUEST_LIMIT
    today = _today()
    try:
        with _lock, database.transaction() as cur:
            if not limit:
                cur.execute(
                    "INSERT INTO `llm_request` (`request_day`, `model`) VALUES (%s, %s)",
                    (today, config.LLM_MODEL),
                )
                return True
            # 오늘 건수가 상한 미만일 때만 1행 추가 (확인+추가를 한 문장으로)
            cur.execute(
                "INSERT INTO `llm_request` (`request_day`, `model`) "
                "SELECT %s, %s FROM DUAL "
                "WHERE (SELECT COUNT(*) FROM `llm_request` WHERE `request_day` = %s) < %s",
                (today, config.LLM_MODEL, today, limit),
            )
            return cur.rowcount > 0
    except (database.DatabaseError, database.DatabaseConfigError) as exc:
        logger.warning("LLM 요청 한도 확인 불가 -> 호출하지 않음: %s", type(exc).__name__)
        return False


def record_tokens(input_tokens: int, output_tokens: int) -> None:
    try:
        with database.transaction() as cur:
            cur.execute(
                "INSERT INTO `llm_token_usage` (`usage_day`, `model`, `input_tokens`, `output_tokens`) "
                "VALUES (%s, %s, %s, %s)",
                (_today(), config.LLM_MODEL, input_tokens, output_tokens),
            )
    except (database.DatabaseError, database.DatabaseConfigError) as exc:
        logger.warning("LLM 토큰 사용량 기록 실패: %s", type(exc).__name__)


def snapshot() -> dict:
    today = _today()
    with database.transaction() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM `llm_request` WHERE `request_day` = %s", (today,))
        used = cur.fetchone()["n"]
        cur.execute(
            "SELECT COALESCE(SUM(`input_tokens`), 0) AS i, COALESCE(SUM(`output_tokens`), 0) AS o "
            "FROM `llm_token_usage` WHERE `usage_day` = %s",
            (today,),
        )
        tokens = cur.fetchone()

    limit = config.LLM_DAILY_REQUEST_LIMIT
    return {
        "date_utc": today.isoformat(),
        "model": config.LLM_MODEL,
        "requests": used,
        "daily_limit": limit or None,
        "remaining": max(limit - used, 0) if limit else None,
        "input_tokens": int(tokens["i"]),
        "output_tokens": int(tokens["o"]),
    }

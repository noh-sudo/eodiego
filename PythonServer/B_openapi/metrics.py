"""관광공사 API 호출 계수 (호출마다 1행 INSERT, 조회 시 COUNT)"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone

from shared import database

from . import config

logger = logging.getLogger("B_openapi.kto")

# 한도는 한국 날짜 기준 (서버 시간대와 무관하게 KST)
_KST = timezone(timedelta(hours=9))


def _today() -> date:
    return datetime.now(_KST).date()


def record(operation: str) -> int:
    """호출 1건 기록 후 오늘 누적 수 반환 (기록 실패 시 -1)"""

    today = _today()
    try:
        with database.transaction() as cur:
            cur.execute(
                "INSERT INTO `kto_api_call` (`call_day`, `operation`) VALUES (%s, %s)",
                (today, operation),
            )
            cur.execute("SELECT COUNT(*) AS n FROM `kto_api_call` WHERE `call_day` = %s", (today,))
            total = cur.fetchone()["n"]
    except (database.DatabaseError, database.DatabaseConfigError) as exc:
        logger.warning("KTO 호출 기록 실패 (호출은 계속): %s", type(exc).__name__)
        return -1

    quota = config.KTO_DAILY_QUOTA
    logger.info("KTO %s (오늘 %d%s)", operation, total, f"/{quota}" if quota else "")
    if quota and total == int(quota * 0.9):
        logger.warning("관광공사 API 일일 한도의 90%%를 소모했습니다: %d/%d", total, quota)
    if quota and total == quota:
        logger.warning("관광공사 API 일일 한도에 도달했습니다: %d/%d", total, quota)
    return total


def snapshot(days: int = 7) -> dict:
    """오늘 누적치와 최근 이력"""

    today = _today()
    with database.transaction() as cur:
        cur.execute(
            "SELECT `operation`, COUNT(*) AS n FROM `kto_api_call` WHERE `call_day` = %s GROUP BY `operation`",
            (today,),
        )
        by_operation = {r["operation"]: r["n"] for r in cur.fetchall()}
        cur.execute(
            "SELECT `call_day`, COUNT(*) AS n FROM `kto_api_call` "
            "GROUP BY `call_day` ORDER BY `call_day` DESC LIMIT %s",
            (max(days, 1),),
        )
        history = [{"date": r["call_day"].isoformat(), "total": r["n"]} for r in cur.fetchall()]

    total = sum(by_operation.values())
    quota = config.KTO_DAILY_QUOTA
    return {
        "date": today.isoformat(),
        "total": total,
        "by_operation": by_operation,
        "daily_quota": quota or None,
        "remaining": max(quota - total, 0) if quota else None,
        "history": history,
    }

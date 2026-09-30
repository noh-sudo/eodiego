"""A의 MySQL 접근 계층 (SELECT/INSERT 전용, 삭제·로그아웃은 기록 추가 방식)"""

from __future__ import annotations

from datetime import datetime, timezone

from shared import database
from shared.schemas import PlanItem, SavedPlan


class DuplicateUserError(Exception):
    pass


def ping() -> None:
    """기동 시 DB 접속과 테이블 존재 확인"""

    with database.transaction() as cur:
        cur.execute("SELECT 1 FROM `user` LIMIT 1")


def _utc(epoch_seconds: float) -> datetime:
    """DATETIME은 시간대가 없어 UTC 기준으로 저장·비교"""

    return datetime.fromtimestamp(epoch_seconds, timezone.utc).replace(tzinfo=None)


# --- 회원 ---


def create_user(username: str, password_hash: str) -> int:
    try:
        with database.transaction() as cur:
            cur.execute(
                "INSERT INTO `user` (`username`, `password_hash`) VALUES (%s, %s)",
                (username, password_hash),
            )
            return cur.lastrowid
    except database.IntegrityError as exc:
        raise DuplicateUserError(f"username={username} 이미 존재") from exc


def get_user_by_username(username: str) -> dict | None:
    with database.transaction() as cur:
        cur.execute(
            "SELECT `user_id`, `username`, `password_hash` FROM `user` WHERE `username` = %s",
            (username,),
        )
        return cur.fetchone()


def get_user_by_id(user_id: int) -> dict | None:
    with database.transaction() as cur:
        cur.execute(
            "SELECT `user_id`, `username`, `password_hash` FROM `user` WHERE `user_id` = %s",
            (user_id,),
        )
        return cur.fetchone()


# --- 저장 일정 ---


def create_plan(user_id: int, title: str, travel_date: str, items: list[PlanItem]) -> int:
    with database.transaction() as cur:
        cur.execute(
            "INSERT INTO `plan` (`user_id`, `title`, `travel_date`) VALUES (%s, %s, %s)",
            (user_id, title, travel_date),
        )
        plan_id = cur.lastrowid
        if items:
            cur.executemany(
                "INSERT INTO `plan_item` (`plan_id`, `content_id`, `name`, `item_order`, `visit_time`, `note`) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                [(plan_id, i.content_id, i.name, i.order, i.visit_time, i.note) for i in items],
            )
    return plan_id


# 삭제 기록이 있는 일정 제외 조건
_NOT_DELETED = "NOT EXISTS (SELECT 1 FROM `plan_deletion` d WHERE d.`plan_id` = p.`plan_id`)"


def _items_by_plan(cur, plan_ids: list[int]) -> dict[int, list[PlanItem]]:
    if not plan_ids:
        return {}
    placeholders = ", ".join(["%s"] * len(plan_ids))
    cur.execute(
        "SELECT `plan_id`, `content_id`, `name`, `item_order`, `visit_time`, `note` "
        f"FROM `plan_item` WHERE `plan_id` IN ({placeholders}) ORDER BY `plan_id`, `item_order`",
        plan_ids,
    )
    grouped: dict[int, list[PlanItem]] = {pid: [] for pid in plan_ids}
    for r in cur.fetchall():
        grouped[r["plan_id"]].append(
            PlanItem(
                content_id=r["content_id"], name=r["name"], order=r["item_order"],
                visit_time=r["visit_time"], note=r["note"],
            )
        )
    return grouped


def list_plans(user_id: int) -> list[SavedPlan]:
    with database.transaction() as cur:
        cur.execute(
            "SELECT p.`plan_id`, p.`title`, p.`travel_date` FROM `plan` p "
            f"WHERE p.`user_id` = %s AND {_NOT_DELETED} "
            "ORDER BY p.`created_at` DESC, p.`plan_id` DESC",
            (user_id,),
        )
        plans = cur.fetchall()
        items = _items_by_plan(cur, [p["plan_id"] for p in plans])
    return [
        SavedPlan(plan_id=p["plan_id"], title=p["title"], travel_date=p["travel_date"], items=items[p["plan_id"]])
        for p in plans
    ]


def get_plan(user_id: int, plan_id: int) -> SavedPlan | None:
    with database.transaction() as cur:
        cur.execute(
            "SELECT p.`plan_id`, p.`title`, p.`travel_date` FROM `plan` p "
            f"WHERE p.`plan_id` = %s AND p.`user_id` = %s AND {_NOT_DELETED}",
            (plan_id, user_id),
        )
        plan = cur.fetchone()
        if plan is None:
            return None
        items = _items_by_plan(cur, [plan_id])
    return SavedPlan(plan_id=plan["plan_id"], title=plan["title"], travel_date=plan["travel_date"], items=items[plan_id])


def delete_plan(user_id: int, plan_id: int) -> bool:
    """본인 일정이고 미삭제일 때만 삭제 기록 추가"""

    with database.transaction() as cur:
        cur.execute(
            "INSERT IGNORE INTO `plan_deletion` (`plan_id`, `user_id`) "
            "SELECT p.`plan_id`, p.`user_id` FROM `plan` p "
            f"WHERE p.`plan_id` = %s AND p.`user_id` = %s AND {_NOT_DELETED}",
            (plan_id, user_id),
        )
        return cur.rowcount > 0


# --- 세션 ---


def create_session(token_hash: str, user_id: int, expires_at: float) -> None:
    with database.transaction() as cur:
        cur.execute(
            "INSERT INTO `session` (`token_hash`, `user_id`, `expires_at`) VALUES (%s, %s, %s)",
            (token_hash, user_id, _utc(expires_at)),
        )


def get_session_user(token_hash: str, now: float) -> int | None:
    """유효한 세션이면 user_id, 아니면 None"""

    with database.transaction() as cur:
        cur.execute(
            "SELECT s.`user_id` FROM `session` s "
            "LEFT JOIN `session_revocation` r ON r.`token_hash` = s.`token_hash` "
            "WHERE s.`token_hash` = %s AND s.`expires_at` > %s AND r.`token_hash` IS NULL",
            (token_hash, _utc(now)),
        )
        row = cur.fetchone()
    return row["user_id"] if row else None


def revoke_session(token_hash: str) -> None:
    """존재하는 세션일 때만 폐기 기록 추가"""

    with database.transaction() as cur:
        cur.execute(
            "INSERT IGNORE INTO `session_revocation` (`token_hash`) "
            "SELECT `token_hash` FROM `session` WHERE `token_hash` = %s",
            (token_hash,),
        )

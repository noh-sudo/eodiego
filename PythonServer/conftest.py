"""전체 테스트 공통 설정: .env의 DB_* 계정으로 테스트 DB(eodiego_test) 사용"""

import os
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent


def _load_db_env() -> None:
    env_file = _ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("DB_") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())
    os.environ["DB_NAME"] = os.environ.get("TEST_DB_NAME", "eodiego_test")


_load_db_env()


@pytest.fixture(scope="session")
def mysql_db():
    """테스트 DB 접속과 테이블 확인, 실패 시 건너뜀"""

    from shared import database

    try:
        with database.transaction() as cur:
            cur.execute("SELECT 1 FROM `user` LIMIT 1")
            cur.execute("SELECT 1 FROM `kto_api_call` LIMIT 1")
            cur.execute("SELECT 1 FROM `llm_request` LIMIT 1")
    except Exception as exc:  # noqa: BLE001 - 어떤 이유든 DB가 준비 안 된 것
        pytest.skip(f"MySQL 테스트 DB({os.environ['DB_NAME']}) 사용 불가: {type(exc).__name__}: {exc}")
    return os.environ["DB_NAME"]

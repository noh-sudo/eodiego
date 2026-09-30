import pytest
from fastapi.testclient import TestClient

from A_backend import main


@pytest.fixture
def client(mysql_db):
    # 테이블은 db/schema.sql로 미리 생성돼 있어야 함
    return TestClient(main.app)

"""테스트 보조 함수 (DELETE 권한이 없어 실행마다 고유한 값 생성)"""

from __future__ import annotations

import random
import uuid
from datetime import date, timedelta


def make_unique_name(prefix: str = "t") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def make_unique_day() -> date:
    """다른 테스트와 겹치지 않는 먼 미래 날짜"""

    return date(2100, 1, 1) + timedelta(days=random.randint(0, 2_500_000))

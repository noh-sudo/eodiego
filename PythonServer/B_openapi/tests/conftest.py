"""호출 카운터를 테스트마다 고유한 먼 미래 날짜로 기록"""

import pytest

from B_openapi import metrics
from shared.testing import make_unique_day


@pytest.fixture(autouse=True)
def isolated_metrics_day(monkeypatch):
    day = make_unique_day()
    monkeypatch.setattr(metrics, "_today", lambda: day)
    return day

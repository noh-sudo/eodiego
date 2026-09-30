"""실제 OpenAI 호출 차단(USE_LLM 끔), 사용량은 고유한 먼 미래 날짜로 기록"""

import pytest

from C_ai_planner import config, llm_client, llm_usage
from shared.testing import make_unique_day


@pytest.fixture(autouse=True)
def isolate_llm(monkeypatch):
    monkeypatch.setattr(config, "USE_LLM", False)
    monkeypatch.setattr(llm_client, "_openai_client", None)
    day = make_unique_day()
    monkeypatch.setattr(llm_usage, "_today", lambda: day)
    return day

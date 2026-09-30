"""관광지 이름과 집중률 API 결과 매칭"""

from __future__ import annotations

import re

_PAREN_SUFFIX_RE = re.compile(r"\s*\([^)]*\)\s*$")


def extract_base_name(title: str) -> str:
    """괄호 앞 이름만 추출 (예: 보덕사(제주) -> 보덕사)"""

    return _PAREN_SUFFIX_RE.sub("", title).strip()


def build_signgu_cd(area_cd: str, l_dong_signgu_cd: str) -> str:
    """areaCd + lDongSignguCd -> signguCd (예: 50 + 110 -> 50110)"""

    return f"{area_cd}{l_dong_signgu_cd}"


def match_congestion_candidate(
    candidates: list[dict], exact_name: str
) -> dict | None:
    """정확히 일치하는 후보가 하나일 때만 채택, 불명확하면 None"""

    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]

    exact_matches = [c for c in candidates if c.get("name") == exact_name]
    if len(exact_matches) == 1:
        return exact_matches[0]

    # 후보가 없거나 여러 개면 불명확으로 처리
    return None

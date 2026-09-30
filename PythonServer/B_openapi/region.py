"""지역 선택지와 대표 좌표 (좌표는 이 파일에서만 관리)"""

from __future__ import annotations

from shared.schemas import Region

# 화면 지역 선택지와 위치기반 검색 대표 좌표
SEARCH_REGIONS: list[Region] = [
    Region(code="jeju-si", name="제주시", map_x=126.5312, map_y=33.4996),
    Region(code="seogwipo", name="서귀포", map_x=126.5644, map_y=33.2541),
    Region(code="east", name="서귀 동쪽", map_x=126.9425, map_y=33.4587),
    Region(code="west", name="제주 서쪽", map_x=126.2396, map_y=33.3937),
]


def list_regions() -> list[Region]:
    """화면 지역 칩 선택지 목록"""

    return list(SEARCH_REGIONS)

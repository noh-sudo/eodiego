"""지역 선택지 (B_openapi.md 10절).

지역 좌표를 이 파일 한 곳에서만 관리한다. 다른 파일에 좌표를 하드코딩하지
않는다.
"""

from __future__ import annotations

from shared.schemas import Region

# 화면의 지역 선택지와 위치기반 검색에 쓸 대표 좌표.
# 화면(ui/)이 좌표를 하드코딩하지 않도록 여기서만 관리한다.
# 다른 지역을 추가/삭제하려면 이 목록만 고치면 된다.
SEARCH_REGIONS: list[Region] = [
    Region(code="jeju-si", name="제주시", map_x=126.5312, map_y=33.4996),
    Region(code="seogwipo", name="서귀포", map_x=126.5644, map_y=33.2541),
    Region(code="east", name="서귀 동쪽", map_x=126.9425, map_y=33.4587),
    Region(code="west", name="제주 서쪽", map_x=126.2396, map_y=33.3937),
]


def list_regions() -> list[Region]:
    """화면이 지역 칩으로 그릴 선택지 목록."""

    return list(SEARCH_REGIONS)

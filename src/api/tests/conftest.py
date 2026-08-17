from collections.abc import Callable
from datetime import date

import httpx
import pytest
from pydantic import SecretStr

from app.main import create_app
from app.settings import Settings


@pytest.fixture
def fixed_today() -> Callable[[], date]:
    return lambda: date(2026, 8, 17)


@pytest.fixture
def settings() -> Settings:
    return Settings(
        neis_base_url="https://open.neis.go.kr",
        neis_api_key=SecretStr("test-key"),
        allowed_origins="https://example.test",
    )


@pytest.fixture
def school_row() -> dict[str, object]:
    return {
        "ATPT_OFCDC_SC_CODE": "B10",
        "ATPT_OFCDC_SC_NM": "서울특별시교육청",
        "SD_SCHUL_CODE": "7010569",
        "SCHUL_NM": "서울고등학교",
        "SCHUL_KND_SC_NM": "고등학교",
        "LCTN_SC_NM": "서울특별시",
        "ORG_RDNMA": "서울특별시 서초구 효령로",
        "ORG_RDNDA": "197",
    }


@pytest.fixture
def meal_row() -> dict[str, object]:
    return {
        "ATPT_OFCDC_SC_CODE": "B10",
        "SD_SCHUL_CODE": "7010569",
        "SCHUL_NM": "서울고등학교",
        "MMEAL_SC_CODE": "2",
        "MLSV_YMD": "20260817",
        "DDISH_NM": "현미밥<br/>된장국<br>닭갈비 (1.5.6.)",
        "CAL_INFO": "742.3 Kcal",
        "NTR_INFO": "탄수화물(g) : 108.2<br/>단백질(g) : 35.1",
        "ORPLC_INFO": "쌀 : 국내산<br/>닭고기 : 국내산",
        "MLSV_FGR": 520.0,
    }


def neis_list(resource: str, rows: list[dict[str, object]]) -> dict[str, object]:
    return {
        resource: [
            {
                "head": [
                    {"list_total_count": len(rows)},
                    {"RESULT": {"CODE": "INFO-000", "MESSAGE": "정상 처리"}},
                ]
            },
            {"row": rows},
        ]
    }


@pytest.fixture
def client_factory(settings, fixed_today):
    def factory(handler: httpx.MockTransport):
        return create_app(settings=settings, transport=handler, today=fixed_today)

    return factory

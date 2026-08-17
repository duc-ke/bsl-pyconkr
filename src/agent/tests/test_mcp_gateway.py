import pytest

from app.mcp_gateway import McpGatewayError, _map_meal, _rows
from app.models import SchoolOption


def test_empty_neis_result_maps_to_empty_rows() -> None:
    payload = {"RESULT": {"CODE": "INFO-200", "MESSAGE": "데이터 없음"}}
    assert _rows(payload, "mealServiceDietInfo") == []


def test_meal_mapping_preserves_only_provided_neis_data() -> None:
    school = SchoolOption(
        education_office_code="B10",
        school_code="7010569",
        name="서울고등학교",
    )
    meal = _map_meal(
        school,
        {
            "DDISH_NM": "현미밥<br/>된장국",
            "CAL_INFO": "742.3 Kcal",
            "NTR_INFO": "단백질(g) : 35.1",
            "ORPLC_INFO": "쌀 : 국내산",
            "MLSV_FGR": 520,
        },
    )

    assert meal.dishes == ["현미밥", "된장국"]
    assert meal.serving_count == 520


def test_invalid_mcp_payload_is_not_treated_as_empty() -> None:
    with pytest.raises(McpGatewayError, match="missing schoolInfo"):
        _rows({}, "schoolInfo")

from app.errors import AppError
from app.mappers import (
    map_meal,
    map_school,
    parse_calorie,
    parse_nutrition,
    parse_origins,
    split_br,
)
from app.models.neis import NeisMeal, NeisSchool


def test_maps_school_and_combines_optional_address(school_row):
    school = map_school(NeisSchool.model_validate(school_row))

    assert school.name == "서울고등학교"
    assert school.address == "서울특별시 서초구 효령로 197"

    school_row["ORG_RDNMA"] = None
    school_row["ORG_RDNDA"] = None
    assert map_school(NeisSchool.model_validate(school_row)).address is None


def test_safely_splits_br_and_removes_markup():
    assert split_br(
        "현미밥<br>된장국<BR />닭갈비 (1.5.)<br/>"
        "<script>alert(1)</script><br>&lt;b&gt;표시&lt;/b&gt;"
    ) == ["현미밥", "된장국", "닭갈비 (1.5.)", "alert(1)", "표시"]


def test_parses_optional_meal_fields():
    assert parse_calorie("742.3 Kcal").amount == 742.3
    assert parse_calorie("알 수 없음") is None
    assert [
        item.model_dump()
        for item in parse_nutrition(
            "탄수화물(g) : 108.2<br/>단백질: 35.1 g<br/>잘못된 행"
        )
    ] == [
        {"name": "탄수화물", "amount": 108.2, "unit": "g"},
        {"name": "단백질", "amount": 35.1, "unit": "g"},
    ]
    assert [
        item.model_dump()
        for item in parse_origins(
            "쌀 : 국내산<br/>닭고기:국내산<br/>잘못된 행"
        )
    ] == [
        {"ingredient": "쌀", "origin": "국내산"},
        {"ingredient": "닭고기", "origin": "국내산"},
    ]


def test_maps_meal_and_rejects_critical_malformed_data(meal_row):
    meal = map_meal(NeisMeal.model_validate(meal_row))

    assert meal.date.isoformat() == "2026-08-17"
    assert meal.dishes == ["현미밥", "된장국", "닭갈비 (1.5.6.)"]
    assert meal.serving_count == 520

    meal_row["MLSV_YMD"] = "20260230"
    try:
        map_meal(NeisMeal.model_validate(meal_row))
    except AppError as error:
        assert error.code == "NEIS_BAD_RESPONSE"
    else:
        raise AssertionError("invalid NEIS meal date was accepted")


def test_rejects_non_lunch_rows(meal_row):
    meal_row["MMEAL_SC_CODE"] = "1"
    try:
        map_meal(NeisMeal.model_validate(meal_row))
    except AppError as error:
        assert error.status == 502
    else:
        raise AssertionError("non-lunch row was accepted")

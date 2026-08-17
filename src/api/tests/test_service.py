from datetime import date

import pytest

from app.errors import AppError
from app.models.neis import NeisMeal, NeisSchool
from app.services.meals import MealService, allowed_date_range


class StubNeis:
    def __init__(self, schools=None, meals=None):
        self.schools = schools or []
        self.meals = meals or []
        self.school_call = None
        self.meal_call = None
        self.school_lookup_call = None

    async def search_schools(self, query, page, page_size):
        self.school_call = (query, page, page_size)
        return self.schools, len(self.schools)

    async def get_meals(
        self, education_office_code, school_code, from_date, to_date
    ):
        self.meal_call = (
            education_office_code,
            school_code,
            from_date,
            to_date,
        )
        return self.meals

    async def get_school(self, education_office_code, school_code):
        self.school_lookup_call = (education_office_code, school_code)
        return self.schools[0]


@pytest.mark.asyncio
async def test_trims_school_query(school_row):
    gateway = StubNeis(schools=[NeisSchool.model_validate(school_row)])
    service = MealService(gateway, lambda: date(2026, 8, 17))

    response = await service.search_schools("  서울  ", 2, 10)

    assert gateway.school_call == ("서울", 2, 10)
    assert response.pagination.total_count == 1


@pytest.mark.asyncio
async def test_rejects_trimmed_short_school_query():
    service = MealService(StubNeis(), lambda: date(2026, 8, 17))

    with pytest.raises(AppError) as raised:
        await service.search_schools("  가  ", 1, 20)

    assert raised.value.code == "INVALID_QUERY"


@pytest.mark.asyncio
async def test_rejects_reversed_and_out_of_policy_ranges_before_neis():
    gateway = StubNeis()
    service = MealService(gateway, lambda: date(2026, 8, 17))

    with pytest.raises(AppError) as reversed_error:
        await service.get_meals(
            "B10", "7010569", date(2026, 8, 17), date(2026, 8, 16)
        )
    assert reversed_error.value.code == "INVALID_DATE_RANGE"

    with pytest.raises(AppError) as range_error:
        await service.get_meals(
            "B10", "7010569", date(2026, 6, 30), date(2026, 8, 17)
        )
    assert range_error.value.code == "DATE_OUT_OF_ALLOWED_RANGE"
    assert gateway.meal_call is None


@pytest.mark.asyncio
async def test_forces_lunch_query_and_sorts_results(meal_row):
    later = meal_row.copy()
    later["MLSV_YMD"] = "20260817"
    earlier = meal_row.copy()
    earlier["MLSV_YMD"] = "20260811"
    gateway = StubNeis(
        meals=[
            NeisMeal.model_validate(later),
            NeisMeal.model_validate(earlier),
        ]
    )
    service = MealService(gateway, lambda: date(2026, 8, 17))

    response = await service.get_meals(
        "B10", "7010569", date(2026, 8, 11), date(2026, 8, 17)
    )

    assert gateway.meal_call == ("B10", "7010569", "20260811", "20260817")
    assert [item.date.isoformat() for item in response.items] == [
        "2026-08-11",
        "2026-08-17",
    ]
    assert response.meal_type == "LUNCH"


@pytest.mark.asyncio
async def test_empty_meals_resolve_selected_school_name(school_row):
    gateway = StubNeis(
        schools=[NeisSchool.model_validate(school_row)],
        meals=[],
    )
    service = MealService(gateway, lambda: date(2026, 8, 17))

    response = await service.get_meals(
        "B10", "7010569", date(2026, 8, 11), date(2026, 8, 17)
    )

    assert response.school.name == "서울고등학교"
    assert response.items == []
    assert gateway.school_lookup_call == ("B10", "7010569")


def test_allowed_range_handles_january_year_boundary():
    assert allowed_date_range(date(2027, 1, 4)) == (
        date(2026, 12, 1),
        date(2027, 1, 31),
    )

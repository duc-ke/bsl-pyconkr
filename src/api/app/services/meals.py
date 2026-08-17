import calendar
from collections.abc import Callable
from datetime import date
from typing import Protocol

from app.errors import AppError, bad_neis_response, invalid_query
from app.mappers import map_meal, map_school
from app.models.internal import (
    DateRange,
    FieldError,
    MealSearchResponse,
    Pagination,
    SchoolSearchResponse,
    SelectedSchool,
)
from app.models.neis import NeisMeal, NeisSchool


class NeisGateway(Protocol):
    async def search_schools(
        self, query: str, page: int, page_size: int
    ) -> tuple[list[NeisSchool], int]: ...

    async def get_meals(
        self,
        education_office_code: str,
        school_code: str,
        from_date: str,
        to_date: str,
    ) -> list[NeisMeal]: ...

    async def get_school(
        self, education_office_code: str, school_code: str
    ) -> NeisSchool: ...


class MealService:
    def __init__(
        self,
        neis: NeisGateway,
        today: Callable[[], date],
    ) -> None:
        self._neis = neis
        self._today = today

    async def search_schools(
        self, query: str, page: int, page_size: int
    ) -> SchoolSearchResponse:
        cleaned = query.strip()
        if not 2 <= len(cleaned) <= 100:
            raise invalid_query(
                "검색어는 앞뒤 공백을 제거한 뒤 2자 이상 100자 이하여야 합니다."
            )
        rows, total_count = await self._neis.search_schools(
            cleaned, page, page_size
        )
        return SchoolSearchResponse(
            items=[map_school(row) for row in rows],
            pagination=Pagination(
                page=page,
                page_size=page_size,
                total_count=total_count,
            ),
        )

    async def get_meals(
        self,
        education_office_code: str,
        school_code: str,
        from_date: date,
        to_date: date,
    ) -> MealSearchResponse:
        if to_date < from_date:
            raise AppError(
                status=422,
                code="INVALID_DATE_RANGE",
                title="잘못된 날짜 범위",
                detail="종료일은 시작일보다 빠를 수 없습니다.",
                problem_type="invalid-date-range",
                errors=[
                    FieldError(
                        field="to",
                        message="to must be on or after from",
                    )
                ],
            )
        allowed_start, allowed_end = allowed_date_range(self._today())
        errors = []
        if not allowed_start <= from_date <= allowed_end:
            errors.append(
                FieldError(
                    field="from",
                    message=(
                        "from must be within the current or immediately "
                        "previous month"
                    ),
                )
            )
        if not allowed_start <= to_date <= allowed_end:
            errors.append(
                FieldError(
                    field="to",
                    message=(
                        "to must be within the current or immediately "
                        "previous month"
                    ),
                )
            )
        if errors:
            raise AppError(
                status=422,
                code="DATE_OUT_OF_ALLOWED_RANGE",
                title="조회할 수 없는 날짜 범위",
                detail=(
                    "조회 기간은 현재 달 또는 바로 이전 달 안에서 "
                    "선택해야 합니다."
                ),
                problem_type="date-out-of-allowed-range",
                errors=errors,
            )

        rows = await self._neis.get_meals(
            education_office_code,
            school_code,
            from_date.strftime("%Y%m%d"),
            to_date.strftime("%Y%m%d"),
        )
        for row in rows:
            if (
                row.ATPT_OFCDC_SC_CODE != education_office_code
                or row.SD_SCHUL_CODE != school_code
            ):
                raise bad_neis_response()
        items = sorted((map_meal(row) for row in rows), key=lambda meal: meal.date)
        if any(not from_date <= item.date <= to_date for item in items):
            raise bad_neis_response()
        if rows:
            school_name = rows[0].SCHUL_NM
        else:
            school = await self._neis.get_school(
                education_office_code, school_code
            )
            school_name = school.SCHUL_NM
        return MealSearchResponse(
            school=SelectedSchool(
                education_office_code=education_office_code,
                school_code=school_code,
                name=school_name,
            ),
            range=DateRange(from_=from_date, to=to_date),
            meal_type="LUNCH",
            items=items,
        )


def allowed_date_range(today: date) -> tuple[date, date]:
    if today.month == 1:
        previous_month = 12
        previous_year = today.year - 1
    else:
        previous_month = today.month - 1
        previous_year = today.year
    start = date(previous_year, previous_month, 1)
    end = date(
        today.year,
        today.month,
        calendar.monthrange(today.year, today.month)[1],
    )
    return start, end

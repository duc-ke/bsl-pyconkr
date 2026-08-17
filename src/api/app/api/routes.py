from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_meal_service
from app.models.internal import (
    MealSearchResponse,
    ProblemDetails,
    SchoolSearchResponse,
)
from app.services.meals import MealService

router = APIRouter()

PROBLEM_RESPONSES = {
    status: {
        "model": ProblemDetails,
        "content": {"application/problem+json": {}},
    }
    for status in (400, 422, 500, 502, 503, 504)
}


@router.get(
    "/schools",
    response_model=SchoolSearchResponse,
    operation_id="searchSchools",
    summary="학교 검색",
    responses=PROBLEM_RESPONSES,
)
async def search_schools(
    query: Annotated[
        str,
        Query(
            description="학교 이름의 일부. 앞뒤 공백 제거 후 2~100자",
        ),
    ],
    page: Annotated[int, Query(ge=1, description="페이지 번호")] = 1,
    page_size: Annotated[
        int,
        Query(alias="pageSize", ge=1, le=100, description="페이지당 결과 수"),
    ] = 20,
    service: MealService = Depends(get_meal_service),
) -> SchoolSearchResponse:
    return await service.search_schools(query, page, page_size)


@router.get(
    "/meals",
    response_model=MealSearchResponse,
    operation_id="searchMeals",
    summary="중식 조회",
    responses=PROBLEM_RESPONSES,
)
async def search_meals(
    education_office_code: Annotated[
        str,
        Query(
            alias="educationOfficeCode",
            min_length=3,
            max_length=3,
            pattern=r"^[A-Z0-9]{3}$",
            description="NEIS 시도교육청 코드",
        ),
    ],
    school_code: Annotated[
        str,
        Query(
            alias="schoolCode",
            min_length=7,
            max_length=7,
            pattern=r"^\d{7}$",
            description="NEIS 학교 행정표준코드",
        ),
    ],
    from_date: Annotated[
        date,
        Query(alias="from", description="조회 시작일"),
    ],
    to_date: Annotated[
        date,
        Query(alias="to", description="조회 종료일"),
    ],
    service: MealService = Depends(get_meal_service),
) -> MealSearchResponse:
    return await service.get_meals(
        education_office_code,
        school_code,
        from_date,
        to_date,
    )

from datetime import date
from typing import Literal

from pydantic import AnyUrl, BaseModel, ConfigDict, Field


def to_camel(value: str) -> str:
    parts = value.split("_")
    return parts[0] + "".join(part.capitalize() for part in parts[1:])


class ApiModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
    )


class SchoolSummary(ApiModel):
    education_office_code: str
    education_office_name: str
    school_code: str
    name: str
    school_type: str
    region: str
    address: str | None


class Pagination(ApiModel):
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total_count: int = Field(ge=0)


class SchoolSearchResponse(ApiModel):
    items: list[SchoolSummary]
    pagination: Pagination


class SelectedSchool(ApiModel):
    education_office_code: str
    school_code: str
    name: str


class DateRange(ApiModel):
    from_: date = Field(alias="from")
    to: date


class Calorie(ApiModel):
    amount: float
    unit: Literal["kcal"]


class Nutrient(ApiModel):
    name: str
    amount: float
    unit: str


class IngredientOrigin(ApiModel):
    ingredient: str
    origin: str


class Meal(ApiModel):
    date: date
    dishes: list[str]
    calorie: Calorie | None
    nutrition: list[Nutrient]
    origin_info: list[IngredientOrigin]
    serving_count: float | None


class MealSearchResponse(ApiModel):
    school: SelectedSchool
    range: DateRange
    meal_type: Literal["LUNCH"]
    items: list[Meal]


class FieldError(ApiModel):
    field: str
    message: str


class ProblemDetails(ApiModel):
    type: AnyUrl
    title: str
    status: int
    detail: str
    instance: str
    code: str
    errors: list[FieldError] | None = None
    trace_id: str

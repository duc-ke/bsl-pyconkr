from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

AreaName = Literal["nutrition_balance", "healthiness", "ingredient_quality"]


def to_camel(value: str) -> str:
    parts = value.split("_")
    return parts[0] + "".join(part.capitalize() for part in parts[1:])


class ApiModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
    )


class SchoolOption(ApiModel):
    education_office_code: str = Field(min_length=3, max_length=3)
    school_code: str = Field(min_length=7, max_length=7)
    name: str = Field(min_length=1)
    school_type: str | None = None
    region: str | None = None


class ComparisonRequest(ApiModel):
    schools: list[SchoolOption]
    date: date
    prompt: str = Field(min_length=1, max_length=4000)

    @model_validator(mode="after")
    def validate_schools(self) -> ComparisonRequest:
        if len(self.schools) != 2:
            raise ValueError("exactly two schools must be selected")
        identifiers = {
            (school.education_office_code, school.school_code)
            for school in self.schools
        }
        if len(identifiers) != 2:
            raise ValueError("two different schools must be selected")
        return self


class MealData(ApiModel):
    school: SchoolOption
    dishes: list[str]
    calorie: str | None = None
    nutrition: str | None = None
    origin_info: str | None = None
    serving_count: float | None = None


class PreparedComparison(ApiModel):
    request: ComparisonRequest
    meals: list[MealData]


class SchoolAreaEvaluation(ApiModel):
    school_code: str
    score: int = Field(ge=1, le=5)
    rationale: str = Field(min_length=1)
    evidence: list[str] = Field(min_length=1)
    improvements: list[str] = Field(min_length=1)


class AreaEvaluation(ApiModel):
    area: AreaName
    schools: list[SchoolAreaEvaluation]

    @model_validator(mode="after")
    def validate_school_count(self) -> AreaEvaluation:
        if len(self.schools) != 2:
            raise ValueError("an area evaluation must contain two schools")
        if len({school.school_code for school in self.schools}) != 2:
            raise ValueError("an area evaluation must contain two different schools")
        return self


class WeightedAreaResult(ApiModel):
    area: AreaName
    weight: int
    rating: int
    weighted_score: float
    rationale: str
    evidence: list[str]
    improvements: list[str]


class SchoolScore(ApiModel):
    school: SchoolOption
    areas: list[WeightedAreaResult]
    total_score: float


class ScoredComparison(ApiModel):
    request: ComparisonRequest
    meals: list[MealData]
    schools: list[SchoolScore]


class FinalReview(ApiModel):
    summary: str = Field(min_length=1)
    school_improvements: dict[str, list[str]]
    quality_warnings: list[str] = Field(default_factory=list)


class Outcome(ApiModel):
    status: Literal["WIN", "TIE"]
    winner_school_code: str | None = None
    loser_school_code: str | None = None


class ComparisonResult(ApiModel):
    date: date
    schools: list[SchoolScore]
    outcome: Outcome
    summary: str
    school_improvements: dict[str, list[str]]
    quality_warnings: list[str]
    disclaimer: str = "이 분석은 영양사의 전문 진단을 대체하지 않습니다."

import asyncio
import json
from datetime import date
from types import SimpleNamespace

import pytest
from agent_framework import Message

from app.config import Settings
from app.models import ComparisonRequest, ComparisonResult, MealData, SchoolOption
from app.workflow import create_workflow


SCHOOLS = [
    SchoolOption(
        education_office_code="B10",
        school_code="7010569",
        name="서울고등학교",
        school_type="고등학교",
        region="서울특별시",
    ),
    SchoolOption(
        education_office_code="C10",
        school_code="7150658",
        name="부산고등학교",
        school_type="고등학교",
        region="부산광역시",
    ),
]


class FakeGateway:
    async def get_meal(
        self,
        school: SchoolOption,
        target_date: str,
    ) -> MealData | None:
        return MealData(
            school=school,
            dishes=["현미밥", "된장국", "닭갈비"],
            calorie="742.3 Kcal",
            nutrition="단백질(g) : 35.1",
            origin_info="쌀 : 국내산",
            serving_count=520,
        )


class FakeExpertRunner:
    def __init__(
        self,
        area: str,
        score_by_school: dict[str, int],
        concurrency: dict[str, int],
    ) -> None:
        self._area = area
        self._score_by_school = score_by_school
        self._concurrency = concurrency
        self.stopped = False

    async def run(self, _messages: str, **_kwargs):
        self._concurrency["active"] += 1
        self._concurrency["maximum"] = max(
            self._concurrency["maximum"],
            self._concurrency["active"],
        )
        await asyncio.sleep(0.01)
        self._concurrency["active"] -= 1
        payload = {
            "area": self._area,
            "schools": [
                {
                    "schoolCode": school.school_code,
                    "score": self._score_by_school[school.school_code],
                    "rationale": f"{self._area} 평가",
                    "evidence": ["NEIS 입력 근거"],
                    "improvements": ["구성 개선"],
                }
                for school in SCHOOLS
            ],
        }
        return SimpleNamespace(text=json.dumps(payload, ensure_ascii=False))

    async def stop(self) -> None:
        self.stopped = True


class FakeReviewer:
    def __init__(self) -> None:
        self.stopped = False

    async def run(self, _messages: str, **_kwargs):
        return SimpleNamespace(
            text=json.dumps(
                {
                    "summary": "서울고등학교가 총점에서 앞섭니다.",
                    "schoolImprovements": {
                        "7010569": ["채소 반찬을 보강하세요."],
                        "7150658": ["나트륨 부담을 줄이세요."],
                    },
                    "qualityWarnings": [],
                },
                ensure_ascii=False,
            )
        )

    async def stop(self) -> None:
        self.stopped = True


@pytest.mark.integration
async def test_workflow_runs_experts_concurrently_and_scores_in_code() -> None:
    concurrency = {"active": 0, "maximum": 0}
    area_scores = {
        "nutrition_balance": {"7010569": 5, "7150658": 3},
        "healthiness": {"7010569": 4, "7150658": 3},
        "ingredient_quality": {"7010569": 4, "7150658": 2},
    }
    runners = {
        area: FakeExpertRunner(area, scores, concurrency)
        for area, scores in area_scores.items()
    }
    runners["final_reviewer"] = FakeReviewer()
    workflow = create_workflow(
        settings=Settings(),
        gateway=FakeGateway(),
        today=lambda: date(2026, 8, 17),
        runners=runners,
    )
    request = ComparisonRequest(
        schools=SCHOOLS,
        date=date(2026, 8, 17),
        prompt="두 학교 급식을 루브릭에 따라 비교해 주세요.",
    )

    events = await workflow.run(
        [
            Message(
                "user",
                contents=[request.model_dump_json(by_alias=True)],
            )
        ]
    )

    outputs = events.get_outputs()
    assert len(outputs) == 1
    result = ComparisonResult.model_validate_json(outputs[0])
    assert concurrency["maximum"] == 3
    assert [school.total_score for school in result.schools] == [89.0, 55.0]
    assert result.outcome.status == "WIN"
    assert result.outcome.winner_school_code == "7010569"
    assert [area.weight for area in result.schools[0].areas] == [45, 30, 25]
    assert all(runner.stopped for runner in runners.values())


@pytest.mark.unit
def test_request_requires_two_different_schools() -> None:
    with pytest.raises(ValueError, match="two different schools"):
        ComparisonRequest(
            schools=[SCHOOLS[0], SCHOOLS[0]],
            date=date(2026, 8, 17),
            prompt="비교",
        )

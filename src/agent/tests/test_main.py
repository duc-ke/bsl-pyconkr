import json
from datetime import date
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.models import MealData, SchoolOption


def school(index: int) -> SchoolOption:
    return SchoolOption(
        education_office_code="B10",
        school_code=f"{index:07d}",
        name=f"테스트학교 {index}",
    )


def test_health_and_school_candidates() -> None:
    available = [school(index) for index in range(12)]

    async def load_schools() -> list[SchoolOption]:
        return available

    app = create_app(
        settings=Settings(),
        school_loader=load_schools,
        sample_schools=lambda schools, count: schools[:count],
        today=lambda: date(2026, 8, 17),
        runners={
            area: FakeRunner(area)
            for area in (
                "nutrition_balance",
                "healthiness",
                "ingredient_quality",
            )
        }
        | {"final_reviewer": FakeRunner()},
    )

    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok"}
        response = client.get("/schools")

    assert response.status_code == 200
    assert len(response.json()) == 10
    assert response.json()[0]["schoolCode"] == "0000000"


class FakeGateway:
    async def get_meal(
        self,
        selected_school: SchoolOption,
        _target_date: str,
    ) -> MealData:
        return MealData(
            school=selected_school,
            dishes=["현미밥", "된장국"],
            calorie="700 Kcal",
            nutrition="단백질(g) : 30",
            origin_info="쌀 : 국내산",
            serving_count=500,
        )


class FakeRunner:
    def __init__(self, area: str | None = None) -> None:
        self._area = area

    async def run(self, _messages: str, **_kwargs):
        if self._area is None:
            payload = {
                "summary": "첫 번째 학교가 총점에서 앞섭니다.",
                "schoolImprovements": {
                    "7010569": ["채소 반찬 보강"],
                    "7150658": ["나트륨 관리"],
                },
                "qualityWarnings": [],
            }
        else:
            payload = {
                "area": self._area,
                "schools": [
                    {
                        "schoolCode": code,
                        "score": score,
                        "rationale": "입력 데이터 기반 평가",
                        "evidence": ["NEIS 근거"],
                        "improvements": ["구성 개선"],
                    }
                    for code, score in (("7010569", 5), ("7150658", 3))
                ],
            }
        return SimpleNamespace(text=json.dumps(payload, ensure_ascii=False))

    async def stop(self) -> None:
        pass


def test_ag_ui_endpoint_streams_workflow_steps_and_result() -> None:
    runners = {
        area: FakeRunner(area)
        for area in (
            "nutrition_balance",
            "healthiness",
            "ingredient_quality",
        )
    }
    runners["final_reviewer"] = FakeRunner()
    app = create_app(
        settings=Settings(),
        gateway=FakeGateway(),
        today=lambda: date(2026, 8, 17),
        runners=runners,
    )
    request = {
        "schools": [
            {
                "educationOfficeCode": "B10",
                "schoolCode": "7010569",
                "name": "서울고등학교",
            },
            {
                "educationOfficeCode": "C10",
                "schoolCode": "7150658",
                "name": "부산고등학교",
            },
        ],
        "date": "2026-08-17",
        "prompt": "두 학교를 비교해 주세요.",
    }

    with TestClient(app) as client:
        response = client.post(
            "/ag-ui",
            headers={"Accept": "text/event-stream"},
            json={
                "threadId": "test-thread",
                "runId": "test-run",
                "messages": [
                    {
                        "id": "message-1",
                        "role": "user",
                        "content": json.dumps(request, ensure_ascii=False),
                    }
                ],
                "tools": [],
                "context": [],
                "state": {},
            },
        )

    assert response.status_code == 200
    assert "STEP_STARTED" in response.text
    assert "score_aggregator" in response.text
    assert "RUN_FINISHED" in response.text
    assert '\\"totalScore\\":100.0' in response.text

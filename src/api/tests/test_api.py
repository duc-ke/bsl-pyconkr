import httpx
import pytest

from tests.conftest import neis_list


async def request_app(app, method: str, path: str, **kwargs) -> httpx.Response:
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            return await client.request(method, path, **kwargs)


@pytest.mark.asyncio
async def test_health_is_ready_and_has_trace_id(
    client_factory,
):
    app = client_factory(
        httpx.MockTransport(lambda request: httpx.Response(500))
    )

    response = await request_app(
        app,
        "GET",
        "/health",
        headers={"X-Trace-ID": "test-trace-1234"},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["X-Trace-ID"] == "test-trace-1234"


@pytest.mark.asyncio
async def test_school_search_returns_paginated_mapped_results(
    client_factory, school_row
):
    observed = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal observed
        observed = request
        return httpx.Response(
            200,
            json=neis_list("schoolInfo", [school_row]),
        )

    app = client_factory(httpx.MockTransport(handler))
    response = await request_app(
        app,
        "GET",
        "/api/v1/schools",
        params={"query": "  서울  ", "page": 1, "pageSize": 20},
    )

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "educationOfficeCode": "B10",
                "educationOfficeName": "서울특별시교육청",
                "schoolCode": "7010569",
                "name": "서울고등학교",
                "schoolType": "고등학교",
                "region": "서울특별시",
                "address": "서울특별시 서초구 효령로 197",
            }
        ],
        "pagination": {"page": 1, "pageSize": 20, "totalCount": 1},
    }
    assert observed.url.params["SCHUL_NM"] == "서울"


@pytest.mark.asyncio
async def test_school_search_empty_is_success(client_factory):
    app = client_factory(
        httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={"RESULT": {"CODE": "INFO-200", "MESSAGE": "데이터 없음"}},
            )
        )
    )

    response = await request_app(
        app, "GET", "/api/v1/schools", params={"query": "없는학교"}
    )

    assert response.status_code == 200
    assert response.json()["items"] == []
    assert response.json()["pagination"]["totalCount"] == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("params", "code"),
    [
        ({"query": "가"}, "INVALID_QUERY"),
        ({"query": "가" * 101}, "INVALID_QUERY"),
        ({"query": "서울", "page": 0}, "VALIDATION_ERROR"),
        ({"query": "서울", "pageSize": 101}, "VALIDATION_ERROR"),
    ],
)
async def test_school_validation_uses_problem_details(
    client_factory, params, code
):
    app = client_factory(
        httpx.MockTransport(lambda request: httpx.Response(500))
    )

    response = await request_app(app, "GET", "/api/v1/schools", params=params)

    assert response.status_code in {400, 422}
    assert response.headers["content-type"].startswith("application/problem+json")
    problem = response.json()
    assert problem["code"] == code
    assert problem["status"] == response.status_code
    assert problem["instance"] == "/api/v1/schools"
    assert problem["traceId"]
    assert "errors" in problem


@pytest.mark.asyncio
async def test_meal_search_maps_and_sorts_results(client_factory, meal_row):
    earlier = meal_row.copy()
    earlier["MLSV_YMD"] = "20260811"
    observed = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal observed
        observed = request
        return httpx.Response(
            200,
            json=neis_list("mealServiceDietInfo", [meal_row, earlier]),
        )

    app = client_factory(httpx.MockTransport(handler))
    response = await request_app(
        app,
        "GET",
        "/api/v1/meals",
        params={
            "educationOfficeCode": "B10",
            "schoolCode": "7010569",
            "from": "2026-08-11",
            "to": "2026-08-17",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["school"] == {
        "educationOfficeCode": "B10",
        "schoolCode": "7010569",
        "name": "서울고등학교",
    }
    assert body["range"] == {"from": "2026-08-11", "to": "2026-08-17"}
    assert body["mealType"] == "LUNCH"
    assert [item["date"] for item in body["items"]] == [
        "2026-08-11",
        "2026-08-17",
    ]
    assert body["items"][0]["calorie"] == {"amount": 742.3, "unit": "kcal"}
    assert body["items"][0]["originInfo"][0] == {
        "ingredient": "쌀",
        "origin": "국내산",
    }
    assert observed.url.params["MMEAL_SC_CODE"] == "2"


@pytest.mark.asyncio
async def test_meal_empty_is_not_an_error(client_factory):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/mealServiceDietInfo"):
            return httpx.Response(
                200,
                json={"RESULT": {"CODE": "INFO-200", "MESSAGE": "데이터 없음"}},
            )
        return httpx.Response(
            200,
            json={
                "schoolInfo": [
                    {
                        "head": [
                            {"list_total_count": 1},
                            {
                                "RESULT": {
                                    "CODE": "INFO-000",
                                    "MESSAGE": "정상 처리",
                                }
                            },
                        ]
                    },
                    {
                        "row": [
                            {
                                "ATPT_OFCDC_SC_CODE": "B10",
                                "ATPT_OFCDC_SC_NM": "서울특별시교육청",
                                "SD_SCHUL_CODE": "7010569",
                                "SCHUL_NM": "서울고등학교",
                                "SCHUL_KND_SC_NM": "고등학교",
                                "LCTN_SC_NM": "서울특별시",
                                "ORG_RDNMA": "서울특별시 서초구 효령로",
                                "ORG_RDNDA": "197",
                            }
                        ]
                    },
                ]
            },
        )

    app = client_factory(httpx.MockTransport(handler))

    response = await request_app(
        app,
        "GET",
        "/api/v1/meals",
        params={
            "educationOfficeCode": "B10",
            "schoolCode": "7010569",
            "from": "2026-08-11",
            "to": "2026-08-17",
        },
    )

    assert response.status_code == 200
    assert response.json()["items"] == []
    assert response.json()["school"]["name"] == "서울고등학교"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("from_date", "to_date", "code"),
    [
        ("2026-08-17", "2026-08-16", "INVALID_DATE_RANGE"),
        ("2026-06-30", "2026-08-17", "DATE_OUT_OF_ALLOWED_RANGE"),
        ("2026-07-01", "2026-09-01", "DATE_OUT_OF_ALLOWED_RANGE"),
    ],
)
async def test_meal_policy_validation_happens_before_neis(
    client_factory, from_date, to_date, code
):
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(500)

    app = client_factory(httpx.MockTransport(handler))
    response = await request_app(
        app,
        "GET",
        "/api/v1/meals",
        params={
            "educationOfficeCode": "B10",
            "schoolCode": "7010569",
            "from": from_date,
            "to": to_date,
        },
    )

    assert response.status_code == 422
    assert response.json()["code"] == code
    assert calls == 0


@pytest.mark.asyncio
async def test_meal_identifier_and_date_format_validation(client_factory):
    app = client_factory(
        httpx.MockTransport(lambda request: httpx.Response(500))
    )

    response = await request_app(
        app,
        "GET",
        "/api/v1/meals",
        params={
            "educationOfficeCode": "bad!",
            "schoolCode": "abc",
            "from": "not-a-date",
            "to": "2026-08-17",
        },
    )

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"
    fields = {item["field"] for item in response.json()["errors"]}
    assert {"educationOfficeCode", "schoolCode", "from"}.issubset(fields)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("handler", "status", "code"),
    [
        (
            lambda request: httpx.Response(200, json={"unexpected": []}),
            502,
            "NEIS_BAD_RESPONSE",
        ),
        (
            lambda request: (_ for _ in ()).throw(
                httpx.ConnectError("down", request=request)
            ),
            503,
            "NEIS_UNAVAILABLE",
        ),
        (
            lambda request: (_ for _ in ()).throw(
                httpx.ReadTimeout("slow", request=request)
            ),
            504,
            "NEIS_TIMEOUT",
        ),
    ],
)
async def test_external_failures_are_problem_details(
    client_factory, handler, status, code
):
    app = client_factory(httpx.MockTransport(handler))

    response = await request_app(
        app,
        "GET",
        "/api/v1/schools",
        params={"query": "서울"},
    )

    assert response.status_code == status
    assert response.json()["code"] == code
    assert response.headers["content-type"].startswith("application/problem+json")


@pytest.mark.asyncio
async def test_cors_allows_only_configured_origin(
    client_factory,
):
    app = client_factory(
        httpx.MockTransport(lambda request: httpx.Response(500))
    )

    allowed = await request_app(
        app,
        "OPTIONS",
        "/api/v1/schools",
        headers={
            "Origin": "https://example.test",
            "Access-Control-Request-Method": "GET",
        },
    )
    denied = await request_app(
        app,
        "OPTIONS",
        "/api/v1/schools",
        headers={
            "Origin": "https://evil.test",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "https://example.test"
    assert denied.status_code == 400

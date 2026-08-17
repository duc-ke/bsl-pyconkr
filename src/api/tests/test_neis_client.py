import httpx
import pytest

from app.clients.neis import NeisClient
from app.errors import AppError
from tests.conftest import neis_list


@pytest.mark.asyncio
async def test_client_sends_external_contract_parameters(school_row):
    seen_request = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen_request
        seen_request = request
        return httpx.Response(200, json=neis_list("schoolInfo", [school_row]))

    async with httpx.AsyncClient(
        base_url="https://open.neis.go.kr",
        transport=httpx.MockTransport(handler),
    ) as http:
        rows, total = await NeisClient(http, "secret").search_schools(
            "서울", 2, 20
        )

    assert total == 1
    assert rows[0].SCHUL_NM == "서울고등학교"
    assert seen_request.url.path == "/hub/schoolInfo"
    assert seen_request.url.params["Key"] == "secret"
    assert seen_request.url.params["Type"] == "json"
    assert seen_request.url.params["SCHUL_NM"] == "서울"
    assert seen_request.url.params["pIndex"] == "2"


@pytest.mark.asyncio
async def test_client_forces_neis_lunch_code(meal_row):
    seen_params = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen_params
        seen_params = request.url.params
        return httpx.Response(
            200,
            json=neis_list("mealServiceDietInfo", [meal_row]),
        )

    async with httpx.AsyncClient(
        base_url="https://open.neis.go.kr",
        transport=httpx.MockTransport(handler),
    ) as http:
        await NeisClient(http, "secret").get_meals(
            "B10", "7010569", "20260811", "20260817"
        )

    assert seen_params["MMEAL_SC_CODE"] == "2"
    assert seen_params["MLSV_FROM_YMD"] == "20260811"
    assert seen_params["MLSV_TO_YMD"] == "20260817"


@pytest.mark.asyncio
async def test_client_treats_info_200_as_empty():
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={"RESULT": {"CODE": "INFO-200", "MESSAGE": "데이터 없음"}},
        )
    )
    async with httpx.AsyncClient(
        base_url="https://open.neis.go.kr", transport=transport
    ) as http:
        rows, total = await NeisClient(http, "secret").search_schools(
            "없는학교", 1, 20
        )
    assert rows == []
    assert total == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("handler", "status", "code"),
    [
        (
            lambda request: httpx.Response(200, content=b"not-json"),
            502,
            "NEIS_BAD_RESPONSE",
        ),
        (
            lambda request: httpx.Response(
                200,
                json={"RESULT": {"CODE": "ERROR-300", "MESSAGE": "오류"}},
            ),
            502,
            "NEIS_BAD_RESPONSE",
        ),
        (
            lambda request: httpx.Response(
                200,
                json=neis_list(
                    "schoolInfo",
                    [
                        {
                            "ATPT_OFCDC_SC_CODE": "invalid",
                            "ATPT_OFCDC_SC_NM": "교육청",
                            "SD_SCHUL_CODE": "not-code",
                            "SCHUL_NM": "학교",
                            "SCHUL_KND_SC_NM": "고등학교",
                            "LCTN_SC_NM": "서울",
                        }
                    ],
                ),
            ),
            502,
            "NEIS_BAD_RESPONSE",
        ),
        (
            lambda request: httpx.Response(503),
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
        (
            lambda request: (_ for _ in ()).throw(
                httpx.ConnectError("down", request=request)
            ),
            503,
            "NEIS_UNAVAILABLE",
        ),
    ],
)
async def test_client_distinguishes_external_failures(handler, status, code):
    async with httpx.AsyncClient(
        base_url="https://open.neis.go.kr",
        transport=httpx.MockTransport(handler),
    ) as http:
        with pytest.raises(AppError) as raised:
            await NeisClient(http, "secret").search_schools("서울", 1, 20)

    assert raised.value.status == status
    assert raised.value.code == code

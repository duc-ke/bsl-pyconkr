from typing import Any

import httpx
import pytest
import respx

from app.neis_client import NeisClient, NeisError
from app.openapi import ToolOperation, load_openapi_definition


pytestmark = pytest.mark.integration
_BASE_URL = "https://neis.example.test"


def _operation(name: str) -> ToolOperation:
    return load_openapi_definition().operation(name)


def _success_payload(response_key: str) -> dict[str, Any]:
    return {
        response_key: [
            {
                "head": [
                    {"RESULT": {"CODE": "INFO-000", "MESSAGE": "정상 처리"}}
                ]
            },
            {"row": [{"value": "ok"}]},
        ]
    }


@respx.mock
async def test_injects_secret_defaults_and_lunch_code() -> None:
    route = respx.get(f"{_BASE_URL}/hub/mealServiceDietInfo").mock(
        return_value=httpx.Response(
            200,
            json=_success_payload("mealServiceDietInfo"),
        )
    )
    client = NeisClient(_BASE_URL, "server-secret")
    try:
        await client.execute(
            _operation("getMealServiceDietInfo"),
            {
                "ATPT_OFCDC_SC_CODE": "B10",
                "SD_SCHUL_CODE": "7010115",
                "MMEAL_SC_CODE": "1",
            },
        )
    finally:
        await client.aclose()

    query = route.calls.last.request.url.params
    assert query["Key"] == "server-secret"
    assert query["Type"] == "json"
    assert query["pIndex"] == "1"
    assert query["pSize"] == "100"
    assert query["MMEAL_SC_CODE"] == "2"


@respx.mock
async def test_info_200_is_a_normal_empty_result() -> None:
    payload = {
        "RESULT": {
            "CODE": "INFO-200",
            "MESSAGE": "해당하는 데이터가 없습니다.",
        }
    }
    respx.get(f"{_BASE_URL}/hub/schoolInfo").mock(
        return_value=httpx.Response(200, json=payload)
    )
    client = NeisClient(_BASE_URL, "secret")
    try:
        result = await client.execute(
            _operation("getSchoolInfo"),
            {"SCHUL_NM": "없는학교"},
        )
    finally:
        await client.aclose()

    assert result == payload


@respx.mock
async def test_timeout_maps_to_safe_error() -> None:
    respx.get(f"{_BASE_URL}/hub/schoolInfo").mock(
        side_effect=httpx.ReadTimeout("request contained secret")
    )
    client = NeisClient(_BASE_URL, "do-not-leak")
    try:
        with pytest.raises(NeisError) as caught:
            await client.execute(_operation("getSchoolInfo"), {})
    finally:
        await client.aclose()

    assert caught.value.code == "NEIS_TIMEOUT"
    assert "do-not-leak" not in str(caught.value)


@respx.mock
async def test_neis_business_error_is_preserved() -> None:
    respx.get(f"{_BASE_URL}/hub/schoolInfo").mock(
        return_value=httpx.Response(
            200,
            json={
                "RESULT": {
                    "CODE": "ERROR-290",
                    "MESSAGE": "인증키가 유효하지 않습니다.",
                }
            },
        )
    )
    client = NeisClient(_BASE_URL, "secret")
    try:
        with pytest.raises(NeisError) as caught:
            await client.execute(_operation("getSchoolInfo"), {})
    finally:
        await client.aclose()

    assert caught.value.code == "ERROR-290"
    assert caught.value.message == "인증키가 유효하지 않습니다."

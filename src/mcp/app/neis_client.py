from __future__ import annotations

from typing import Any

import httpx

from .openapi import ToolOperation


class NeisError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


_SUCCESS_CODES = {"INFO-000", "INFO-200"}


class NeisClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        *,
        connect_timeout: float = 3.0,
        read_timeout: float = 10.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = api_key
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url=base_url,
            timeout=httpx.Timeout(
                connect=connect_timeout,
                read=read_timeout,
                write=read_timeout,
                pool=connect_timeout,
            ),
            transport=httpx.AsyncHTTPTransport(local_address="0.0.0.0"),
        )

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def execute(
        self,
        operation: ToolOperation,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        query = {
            **operation.defaults,
            **arguments,
            "Key": self._api_key,
            "Type": "json",
        }
        if operation.name == "getMealServiceDietInfo":
            query["MMEAL_SC_CODE"] = "2"

        try:
            response = await self._client.get(operation.path, params=query)
            response.raise_for_status()
        except httpx.TimeoutException as error:
            raise NeisError(
                "NEIS_TIMEOUT",
                "NEIS 응답이 지연되고 있습니다. 잠시 후 다시 시도해 주세요.",
            ) from error
        except httpx.HTTPStatusError as error:
            raise NeisError(
                "NEIS_HTTP_ERROR",
                f"NEIS가 HTTP {error.response.status_code} 오류를 반환했습니다.",
            ) from error
        except httpx.RequestError as error:
            raise NeisError(
                "NEIS_UNAVAILABLE",
                "NEIS에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요.",
            ) from error

        try:
            payload = response.json()
        except ValueError as error:
            raise NeisError(
                "NEIS_INVALID_RESPONSE",
                "NEIS에서 올바른 JSON 응답을 받지 못했습니다.",
            ) from error
        if not isinstance(payload, dict):
            raise NeisError(
                "NEIS_INVALID_RESPONSE",
                "NEIS JSON 응답은 객체여야 합니다.",
            )

        code, message = _extract_result(payload, operation.response_key)
        if code not in _SUCCESS_CODES:
            raise NeisError(code, message)
        return payload


def _extract_result(
    payload: dict[str, Any],
    response_key: str,
) -> tuple[str, str]:
    result = payload.get("RESULT")
    if isinstance(result, dict):
        return _result_values(result)
    sections = payload.get(response_key)
    if isinstance(sections, list):
        for section in sections:
            if not isinstance(section, dict):
                continue
            heads = section.get("head")
            if not isinstance(heads, list):
                continue
            for head in heads:
                if not isinstance(head, dict):
                    continue
                nested_result = head.get("RESULT")
                if isinstance(nested_result, dict):
                    return _result_values(nested_result)
    raise NeisError(
        "NEIS_INVALID_RESPONSE",
        "NEIS 응답에서 처리 결과를 확인할 수 없습니다.",
    )


def _result_values(result: dict[str, Any]) -> tuple[str, str]:
    code = result.get("CODE")
    message = result.get("MESSAGE")
    if not isinstance(code, str) or not isinstance(message, str):
        raise NeisError(
            "NEIS_INVALID_RESPONSE",
            "NEIS 처리 결과 형식이 올바르지 않습니다.",
        )
    return code, message

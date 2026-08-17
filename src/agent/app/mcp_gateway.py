from __future__ import annotations

from collections.abc import Mapping
from contextlib import AsyncExitStack
from typing import Any

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from .models import MealData, SchoolOption


class McpGatewayError(RuntimeError):
    """Raised when the MCP server returns an invalid or failed result."""


class McpGateway:
    def __init__(self, url: str, *, timeout: float = 20.0) -> None:
        self._url = url
        self._timeout = timeout

    async def list_schools(self) -> list[SchoolOption]:
        payload = await self._call_tool(
            "getSchoolInfo",
            {"pIndex": 1, "pSize": 100},
        )
        rows = _rows(payload, "schoolInfo")
        return [_map_school(row) for row in rows]

    async def get_meal(self, school: SchoolOption, target_date: str) -> MealData | None:
        compact_date = target_date.replace("-", "")
        payload = await self._call_tool(
            "getMealServiceDietInfo",
            {
                "ATPT_OFCDC_SC_CODE": school.education_office_code,
                "SD_SCHUL_CODE": school.school_code,
                "MLSV_FROM_YMD": compact_date,
                "MLSV_TO_YMD": compact_date,
            },
        )
        rows = _rows(payload, "mealServiceDietInfo")
        if not rows:
            return None
        return _map_meal(school, rows[0])

    async def _call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        async with AsyncExitStack() as stack:
            http_client = await stack.enter_async_context(
                httpx.AsyncClient(timeout=self._timeout)
            )
            streams = await stack.enter_async_context(
                streamable_http_client(self._url, http_client=http_client)
            )
            session = await stack.enter_async_context(
                ClientSession(streams[0], streams[1])
            )
            await session.initialize()
            result = await session.call_tool(name, arguments)

        if result.isError:
            message = next(
                (
                    content.text
                    for content in result.content
                    if getattr(content, "type", None) == "text"
                ),
                f"MCP tool {name} failed",
            )
            raise McpGatewayError(message)
        payload = result.structuredContent
        if not isinstance(payload, dict):
            raise McpGatewayError(f"MCP tool {name} returned no structured content")
        return payload


def _rows(payload: Mapping[str, Any], key: str) -> list[dict[str, Any]]:
    result = payload.get("RESULT")
    if isinstance(result, Mapping) and result.get("CODE") == "INFO-200":
        return []
    sections = payload.get(key)
    if not isinstance(sections, list):
        raise McpGatewayError(f"MCP response is missing {key}")
    for section in sections:
        if not isinstance(section, Mapping):
            continue
        rows = section.get("row")
        if isinstance(rows, list):
            if not all(isinstance(row, dict) for row in rows):
                raise McpGatewayError(f"MCP response contains invalid {key} rows")
            return rows
    return []


def _required_string(row: Mapping[str, Any], key: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise McpGatewayError(f"MCP response field {key} is missing")
    return value.strip()


def _optional_string(row: Mapping[str, Any], key: str) -> str | None:
    value = row.get(key)
    return value.strip() if isinstance(value, str) and value.strip() else None


def _map_school(row: Mapping[str, Any]) -> SchoolOption:
    return SchoolOption(
        education_office_code=_required_string(row, "ATPT_OFCDC_SC_CODE"),
        school_code=_required_string(row, "SD_SCHUL_CODE"),
        name=_required_string(row, "SCHUL_NM"),
        school_type=_optional_string(row, "SCHUL_KND_SC_NM"),
        region=_optional_string(row, "LCTN_SC_NM"),
    )


def _map_meal(
    school: SchoolOption,
    row: Mapping[str, Any],
) -> MealData:
    serving_count = row.get("MLSV_FGR")
    if not isinstance(serving_count, (int, float)):
        serving_count = None
    dishes = _optional_string(row, "DDISH_NM")
    return MealData(
        school=school,
        dishes=_split_lines(dishes),
        calorie=_optional_string(row, "CAL_INFO"),
        nutrition=_optional_string(row, "NTR_INFO"),
        origin_info=_optional_string(row, "ORPLC_INFO"),
        serving_count=serving_count,
    )


def _split_lines(value: str | None) -> list[str]:
    if value is None:
        return []
    normalized = value.replace("<br/>", "\n").replace("<br>", "\n")
    return [part.strip() for part in normalized.splitlines() if part.strip()]

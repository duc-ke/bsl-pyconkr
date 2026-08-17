import logging
from collections.abc import Mapping
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.errors import (
    bad_neis_response,
    neis_timeout,
    neis_unavailable,
)
from app.models.neis import NeisMeal, NeisResult, NeisSchool, read_result
from app.observability import log_event

logger = logging.getLogger(__name__)
Row = TypeVar("Row", bound=BaseModel)


class NeisClient:
    def __init__(self, http_client: httpx.AsyncClient, api_key: str) -> None:
        self._http = http_client
        self._api_key = api_key

    async def search_schools(
        self, query: str, page: int, page_size: int
    ) -> tuple[list[NeisSchool], int]:
        payload = await self._get(
            "/hub/schoolInfo",
            {
                "SCHUL_NM": query,
                "pIndex": page,
                "pSize": page_size,
            },
        )
        return self._parse_list(payload, "schoolInfo", NeisSchool)

    async def get_meals(
        self,
        education_office_code: str,
        school_code: str,
        from_date: str,
        to_date: str,
    ) -> list[NeisMeal]:
        payload = await self._get(
            "/hub/mealServiceDietInfo",
            {
                "ATPT_OFCDC_SC_CODE": education_office_code,
                "SD_SCHUL_CODE": school_code,
                "MMEAL_SC_CODE": "2",
                "MLSV_FROM_YMD": from_date,
                "MLSV_TO_YMD": to_date,
                "pIndex": 1,
                "pSize": 100,
            },
        )
        rows, _ = self._parse_list(payload, "mealServiceDietInfo", NeisMeal)
        return rows

    async def get_school(
        self, education_office_code: str, school_code: str
    ) -> NeisSchool:
        payload = await self._get(
            "/hub/schoolInfo",
            {
                "ATPT_OFCDC_SC_CODE": education_office_code,
                "SD_SCHUL_CODE": school_code,
                "pIndex": 1,
                "pSize": 1,
            },
        )
        rows, _ = self._parse_list(payload, "schoolInfo", NeisSchool)
        if len(rows) != 1:
            raise bad_neis_response()
        school = rows[0]
        if (
            school.ATPT_OFCDC_SC_CODE != education_office_code
            or school.SD_SCHUL_CODE != school_code
        ):
            raise bad_neis_response()
        return school

    async def _get(self, path: str, parameters: Mapping[str, str | int]) -> Any:
        params: dict[str, str | int] = {
            "Key": self._api_key,
            "Type": "json",
            **parameters,
        }
        try:
            response = await self._http.get(path, params=params)
        except httpx.TimeoutException as error:
            log_event(logger, logging.WARNING, "neis_request_failed", category="timeout")
            raise neis_timeout() from error
        except httpx.RequestError as error:
            log_event(
                logger,
                logging.WARNING,
                "neis_request_failed",
                category="unavailable",
            )
            raise neis_unavailable() from error

        if response.status_code == 429 or response.status_code >= 500:
            log_event(
                logger,
                logging.WARNING,
                "neis_request_failed",
                category="unavailable",
                upstreamStatus=response.status_code,
            )
            raise neis_unavailable()
        if response.status_code < 200 or response.status_code >= 300:
            log_event(
                logger,
                logging.WARNING,
                "neis_request_failed",
                category="bad_response",
                upstreamStatus=response.status_code,
            )
            raise bad_neis_response()

        try:
            return response.json()
        except ValueError as error:
            log_event(
                logger,
                logging.WARNING,
                "neis_request_failed",
                category="bad_response",
            )
            raise bad_neis_response() from error

    @staticmethod
    def _parse_list(
        payload: Any, resource: str, row_model: type[Row]
    ) -> tuple[list[Row], int]:
        try:
            top_result = read_result(payload)
        except ValidationError as error:
            raise bad_neis_response() from error
        if top_result is not None:
            if top_result.CODE == "INFO-200":
                return [], 0
            raise bad_neis_response()

        if not isinstance(payload, dict):
            raise bad_neis_response()
        sections = payload.get(resource)
        if not isinstance(sections, list):
            raise bad_neis_response()

        head: list[Any] | None = None
        raw_rows: list[Any] | None = None
        for section in sections:
            if not isinstance(section, dict):
                raise bad_neis_response()
            if "head" in section:
                head = section["head"]
            if "row" in section:
                raw_rows = section["row"]

        result, total_count = NeisClient._parse_head(head)
        if result.CODE != "INFO-000":
            if result.CODE == "INFO-200":
                return [], 0
            raise bad_neis_response()
        if not isinstance(raw_rows, list):
            raise bad_neis_response()

        try:
            rows = [row_model.model_validate(row) for row in raw_rows]
        except ValidationError as error:
            raise bad_neis_response() from error
        return rows, total_count

    @staticmethod
    def _parse_head(head: Any) -> tuple[NeisResult, int]:
        if not isinstance(head, list):
            raise bad_neis_response()
        result: NeisResult | None = None
        total_count: int | None = None
        for item in head:
            if not isinstance(item, dict):
                raise bad_neis_response()
            if "RESULT" in item:
                try:
                    result = NeisResult.model_validate(item["RESULT"])
                except ValidationError as error:
                    raise bad_neis_response() from error
            if "list_total_count" in item:
                count = item["list_total_count"]
                if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                    raise bad_neis_response()
                total_count = count
        if result is None or total_count is None:
            raise bad_neis_response()
        return result, total_count

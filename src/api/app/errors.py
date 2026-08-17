from collections.abc import Sequence
from dataclasses import dataclass

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.models.internal import FieldError, ProblemDetails


@dataclass(slots=True)
class AppError(Exception):
    status: int
    code: str
    title: str
    detail: str
    problem_type: str
    errors: Sequence[FieldError] | None = None


def invalid_query(detail: str, field: str = "query") -> AppError:
    return AppError(
        status=400,
        code="INVALID_QUERY",
        title="잘못된 검색 조건",
        detail=detail,
        problem_type="invalid-query",
        errors=[FieldError(field=field, message=detail)],
    )


def bad_neis_response() -> AppError:
    return AppError(
        status=502,
        code="NEIS_BAD_RESPONSE",
        title="외부 서비스 응답 오류",
        detail="NEIS에서 올바른 응답을 받지 못했습니다.",
        problem_type="neis-bad-response",
    )


def neis_unavailable() -> AppError:
    return AppError(
        status=503,
        code="NEIS_UNAVAILABLE",
        title="외부 서비스를 사용할 수 없음",
        detail="NEIS에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요.",
        problem_type="neis-unavailable",
    )


def neis_timeout() -> AppError:
    return AppError(
        status=504,
        code="NEIS_TIMEOUT",
        title="외부 서비스 응답 시간 초과",
        detail="NEIS 응답이 지연되고 있습니다. 잠시 후 다시 시도해 주세요.",
        problem_type="neis-timeout",
    )


def _problem_response(request: Request, error: AppError) -> JSONResponse:
    trace_id = getattr(request.state, "trace_id", "unknown")
    problem = ProblemDetails(
        type=f"https://bsl.example/problems/{error.problem_type}",
        title=error.title,
        status=error.status,
        detail=error.detail,
        instance=request.url.path,
        code=error.code,
        errors=list(error.errors) if error.errors else None,
        trace_id=trace_id,
    )
    return JSONResponse(
        status_code=error.status,
        content=problem.model_dump(mode="json", by_alias=True, exclude_none=True),
        media_type="application/problem+json",
    )


async def app_error_handler(request: Request, error: AppError) -> JSONResponse:
    return _problem_response(request, error)


async def validation_error_handler(
    request: Request, error: RequestValidationError
) -> JSONResponse:
    field_errors = []
    for item in error.errors():
        location = [str(part) for part in item["loc"][1:]]
        field_errors.append(
            FieldError(
                field=".".join(location) or "request",
                message=item["msg"],
            )
        )
    query_fields = {item.field for item in field_errors}
    if "query" in query_fields:
        return _problem_response(
            request,
            invalid_query(
                "검색어는 앞뒤 공백을 제거한 뒤 2자 이상 100자 이하여야 합니다."
            ),
        )
    return _problem_response(
        request,
        AppError(
            status=422,
            code="VALIDATION_ERROR",
            title="요청 값 검증 오류",
            detail="요청 매개변수의 형식 또는 범위를 확인해 주세요.",
            problem_type="validation-error",
            errors=field_errors,
        ),
    )


async def internal_error_handler(request: Request, error: Exception) -> JSONResponse:
    return _problem_response(
        request,
        AppError(
            status=500,
            code="INTERNAL_ERROR",
            title="내부 서버 오류",
            detail="요청을 처리하지 못했습니다.",
            problem_type="internal-error",
        ),
    )

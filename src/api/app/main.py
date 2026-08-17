import logging
import re
import time
import uuid
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import date, datetime
from zoneinfo import ZoneInfo

import httpx
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.clients.neis import NeisClient
from app.errors import (
    AppError,
    app_error_handler,
    internal_error_handler,
    validation_error_handler,
)
from app.observability import log_event, trace_id_context
from app.services.meals import MealService
from app.settings import Settings

logger = logging.getLogger(__name__)
_TRACE_ID = re.compile(r"^[A-Za-z0-9._-]{8,128}$")


def seoul_today() -> date:
    return datetime.now(ZoneInfo("Asia/Seoul")).date()


def create_app(
    settings: Settings | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
    today: Callable[[], date] = seoul_today,
) -> FastAPI:
    configured = settings or Settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        timeout = httpx.Timeout(
            connect=configured.neis_connect_timeout,
            read=configured.neis_read_timeout,
            write=configured.neis_read_timeout,
            pool=configured.neis_connect_timeout,
        )
        client = httpx.AsyncClient(
            base_url=str(configured.neis_base_url).rstrip("/"),
            timeout=timeout,
            transport=transport
            or httpx.AsyncHTTPTransport(local_address="0.0.0.0"),
        )
        application.state.http_client = client
        application.state.meal_service = MealService(
            NeisClient(client, configured.api_key()),
            today=today,
        )
        try:
            yield
        finally:
            await client.aclose()

    application = FastAPI(
        title="급식 배틀 API",
        version="1.0.0",
        summary="학교 검색 및 중식 조회 내부 API",
        openapi_version="3.1.0",
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=configured.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "OPTIONS"],
        allow_headers=["Accept", "Content-Type", "X-Trace-ID"],
        expose_headers=["X-Trace-ID"],
    )

    application.add_exception_handler(AppError, app_error_handler)
    application.add_exception_handler(
        RequestValidationError, validation_error_handler
    )
    application.add_exception_handler(Exception, internal_error_handler)

    @application.middleware("http")
    async def trace_requests(request: Request, call_next):
        supplied_trace_id = request.headers.get("X-Trace-ID", "")
        trace_id = (
            supplied_trace_id
            if _TRACE_ID.fullmatch(supplied_trace_id)
            else uuid.uuid4().hex
        )
        request.state.trace_id = trace_id
        trace_token = trace_id_context.set(trace_id)
        started = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as error:
            response = await internal_error_handler(request, error)
        response.headers["X-Trace-ID"] = trace_id
        log_event(
            logger,
            logging.INFO,
            "request_completed",
            path=request.url.path,
            statusCode=status_code,
            durationMs=round((time.perf_counter() - started) * 1000, 2),
        )
        trace_id_context.reset(trace_token)
        return response

    @application.get("/health", include_in_schema=False)
    async def health() -> JSONResponse:
        return JSONResponse({"status": "ok"})

    application.include_router(router, prefix="/api/v1")

    def custom_openapi() -> dict:
        if application.openapi_schema:
            return application.openapi_schema
        schema = get_openapi(
            title=application.title,
            version=application.version,
            summary=application.summary,
            routes=application.routes,
            openapi_version=application.openapi_version,
        )
        school_parameters = schema["paths"]["/api/v1/schools"]["get"][
            "parameters"
        ]
        query_schema = next(
            parameter["schema"]
            for parameter in school_parameters
            if parameter["name"] == "query"
        )
        query_schema["minLength"] = 2
        query_schema["maxLength"] = 100
        for path in schema["paths"].values():
            for operation in path.values():
                for status, response in operation.get("responses", {}).items():
                    if status == "200":
                        continue
                    content = response.get("content", {})
                    json_schema = content.get("application/json", {}).get("schema")
                    if json_schema:
                        content.setdefault("application/problem+json", {}).setdefault(
                            "schema", json_schema
                        )
                    content.pop("application/json", None)
        application.openapi_schema = schema
        return schema

    application.openapi = custom_openapi
    return application


app = create_app()

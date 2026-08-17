from __future__ import annotations

import random
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import date
from typing import Any

from agent_framework.ag_ui import (
    AgentFrameworkWorkflow,
    add_agent_framework_fastapi_endpoint,
)
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import Settings, seoul_today
from .mcp_gateway import McpGateway
from .models import SchoolOption
from .workflow import AgentRunner, MealGateway, create_workflow


class TransientAgentFrameworkWorkflow(AgentFrameworkWorkflow):
    async def run(self, input_data: dict[str, Any]) -> AsyncIterator[Any]:
        thread_id = self._thread_id_from_input(input_data)
        try:
            async for event in super().run(input_data):
                yield event
        finally:
            self.clear_thread_workflow(thread_id)


def create_app(
    *,
    settings: Settings | None = None,
    gateway: MealGateway | None = None,
    school_loader: Callable[[], Any] | None = None,
    today: Callable[[], date] = seoul_today,
    runners: dict[str, AgentRunner] | None = None,
    sample_schools: Callable[[list[SchoolOption], int], list[SchoolOption]]
    | None = None,
) -> FastAPI:
    configured = settings or Settings()
    resolved_gateway = gateway or McpGateway(
        str(configured.mcp_url),
        timeout=configured.mcp_timeout,
    )
    sampler = sample_schools or random.SystemRandom().sample

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        application.state.gateway = resolved_gateway
        yield

    application = FastAPI(
        title="급식 배틀 멀티 에이전트",
        version="0.1.0",
        lifespan=lifespan,
    )
    if configured.cors_origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=configured.cors_origins,
            allow_credentials=False,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["Content-Type", "Accept"],
        )

    @application.get("/health", include_in_schema=False)
    async def health() -> JSONResponse:
        return JSONResponse({"status": "ok"})

    @application.get("/schools", response_model=list[SchoolOption])
    async def schools(request: Request) -> list[SchoolOption]:
        if school_loader is not None:
            available = await school_loader()
        else:
            available = await request.app.state.gateway.list_schools()
        if len(available) < 10:
            return available
        return sampler(available, 10)

    ag_ui_workflow = TransientAgentFrameworkWorkflow(
        workflow_factory=lambda _thread_id: create_workflow(
            settings=configured,
            gateway=resolved_gateway,
            today=today,
            runners=runners,
        ),
        name="school_lunch_comparison",
        description="세 전문 평가와 최종 품질 게이트로 두 학교 급식을 비교합니다.",
    )
    add_agent_framework_fastapi_endpoint(
        application,
        ag_ui_workflow,
        "/ag-ui",
    )
    return application


app = create_app()

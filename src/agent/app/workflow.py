from __future__ import annotations

import asyncio
import json
from collections.abc import Callable, Mapping
from datetime import date
from typing import Any, Protocol

from agent_framework import (
    Executor,
    Message,
    Workflow,
    WorkflowBuilder,
    WorkflowContext,
    handler,
)
from agent_framework.github import GitHubCopilotAgent, GitHubCopilotOptions
from pydantic import ValidationError
from typing_extensions import Never

from .config import Settings
from .mcp_gateway import McpGateway
from .models import (
    AreaEvaluation,
    AreaName,
    ComparisonRequest,
    ComparisonResult,
    FinalReview,
    MealData,
    Outcome,
    PreparedComparison,
    SchoolScore,
    ScoredComparison,
    WeightedAreaResult,
)

_SCORED_STATE = "scored_comparison"
_AREA_WEIGHTS: dict[AreaName, int] = {
    "nutrition_balance": 45,
    "healthiness": 30,
    "ingredient_quality": 25,
}
_AREA_LABELS: dict[AreaName, str] = {
    "nutrition_balance": "영양 균형",
    "healthiness": "건강성",
    "ingredient_quality": "식재료 및 메뉴 품질",
}


class AgentRunner(Protocol):
    async def run(self, messages: str, **kwargs: Any) -> Any: ...

    async def stop(self) -> None: ...


class MealGateway(Protocol):
    async def get_meal(
        self,
        school: Any,
        target_date: str,
    ) -> MealData | None: ...


def _latest_user_text(messages: list[Message]) -> str:
    for message in reversed(messages):
        role = (
            message.role
            if isinstance(message.role, str)
            else getattr(message.role, "value", "")
        )
        if role == "user" and message.text:
            return message.text
    raise ValueError("AG-UI request must contain a user text message")


def _validate_date(target: date, today: date) -> None:
    current_month = (today.year, today.month)
    previous_year = today.year if today.month > 1 else today.year - 1
    previous_month = today.month - 1 if today.month > 1 else 12
    if (target.year, target.month) not in {
        current_month,
        (previous_year, previous_month),
    }:
        raise ValueError("date must be in the current or immediately previous month")


class PrepareComparison(Executor):
    def __init__(
        self,
        gateway: MealGateway,
        today: Callable[[], date],
    ) -> None:
        super().__init__(id="prepare_comparison")
        self._gateway = gateway
        self._today = today

    @handler
    async def prepare(
        self,
        input_data: list[Message] | str,
        ctx: WorkflowContext[PreparedComparison],
    ) -> None:
        raw_request = (
            input_data if isinstance(input_data, str) else _latest_user_text(input_data)
        )
        try:
            request = ComparisonRequest.model_validate_json(raw_request)
        except ValidationError as error:
            raise ValueError("invalid comparison request") from error
        _validate_date(request.date, self._today())

        meals = await asyncio.gather(
            *(
                self._gateway.get_meal(school, request.date.isoformat())
                for school in request.schools
            )
        )
        if any(meal is None for meal in meals):
            missing = [
                request.schools[index].name
                for index, meal in enumerate(meals)
                if meal is None
            ]
            raise ValueError(
                f"선택한 날짜의 중식 정보가 없습니다: {', '.join(missing)}"
            )
        prepared = PreparedComparison(
            request=request,
            meals=[meal for meal in meals if meal is not None],
        )
        await ctx.send_message(prepared)


class ExpertEvaluator(Executor):
    def __init__(
        self,
        *,
        area: AreaName,
        runner: AgentRunner,
    ) -> None:
        super().__init__(id=f"{area}_expert")
        self._area = area
        self._runner = runner

    @handler
    async def evaluate(
        self,
        prepared: PreparedComparison,
        ctx: WorkflowContext[AreaEvaluation],
    ) -> None:
        try:
            response = await self._runner.run(_expert_prompt(self._area, prepared))
        finally:
            await self._runner.stop()
        text = getattr(response, "text", None)
        if not isinstance(text, str):
            raise RuntimeError(f"{self._area} agent returned no text")
        try:
            evaluation = AreaEvaluation.model_validate_json(_json_text(text))
        except ValidationError as error:
            raise RuntimeError(
                f"{self._area} agent returned invalid structured output"
            ) from error
        if evaluation.area != self._area:
            raise RuntimeError(f"{self._area} agent returned a different area")
        expected_codes = {school.school_code for school in prepared.request.schools}
        actual_codes = {school.school_code for school in evaluation.schools}
        if actual_codes != expected_codes:
            raise RuntimeError(f"{self._area} agent returned unexpected schools")
        await ctx.send_message(evaluation)


class ScoreAggregator(Executor):
    def __init__(self) -> None:
        super().__init__(id="score_aggregator")

    @handler
    async def aggregate(
        self,
        evaluations: list[AreaEvaluation],
        ctx: WorkflowContext[ScoredComparison],
    ) -> None:
        area_map = {evaluation.area: evaluation for evaluation in evaluations}
        if set(area_map) != set(_AREA_WEIGHTS):
            raise RuntimeError("all three rubric areas must be evaluated exactly once")

        prepared: PreparedComparison = ctx.get_state("prepared_comparison")
        school_scores: list[SchoolScore] = []
        for school in prepared.request.schools:
            area_results: list[WeightedAreaResult] = []
            for area, weight in _AREA_WEIGHTS.items():
                evaluation = next(
                    item
                    for item in area_map[area].schools
                    if item.school_code == school.school_code
                )
                area_results.append(
                    WeightedAreaResult(
                        area=area,
                        weight=weight,
                        rating=evaluation.score,
                        weighted_score=round(evaluation.score / 5 * weight, 1),
                        rationale=evaluation.rationale,
                        evidence=evaluation.evidence,
                        improvements=evaluation.improvements,
                    )
                )
            school_scores.append(
                SchoolScore(
                    school=school,
                    areas=area_results,
                    total_score=round(
                        sum(area.weighted_score for area in area_results),
                        1,
                    ),
                )
            )
        scored = ScoredComparison(
            request=prepared.request,
            meals=prepared.meals,
            schools=school_scores,
        )
        ctx.set_state(_SCORED_STATE, scored)
        await ctx.send_message(scored)


class FinalQualityReviewer(Executor):
    def __init__(self, runner: AgentRunner) -> None:
        super().__init__(id="final_quality_reviewer")
        self._runner = runner

    @handler
    async def review(
        self,
        scored: ScoredComparison,
        ctx: WorkflowContext[FinalReview],
    ) -> None:
        try:
            response = await self._runner.run(_review_prompt(scored))
        finally:
            await self._runner.stop()
        text = getattr(response, "text", None)
        if not isinstance(text, str):
            raise RuntimeError("final reviewer returned no text")
        try:
            review = FinalReview.model_validate_json(_json_text(text))
        except ValidationError as error:
            raise RuntimeError(
                "final reviewer returned invalid structured output"
            ) from error
        expected_codes = {school.school.school_code for school in scored.schools}
        if set(review.school_improvements) != expected_codes:
            raise RuntimeError("final reviewer returned unexpected schools")
        await ctx.send_message(review)


class ResultFormatter(Executor):
    def __init__(self) -> None:
        super().__init__(id="result_formatter")

    @handler
    async def format_result(
        self,
        review: FinalReview,
        ctx: WorkflowContext[Never, str],
    ) -> None:
        scored: ScoredComparison = ctx.get_state(_SCORED_STATE)
        first, second = scored.schools
        if first.total_score == second.total_score:
            outcome = Outcome(status="TIE")
        else:
            winner, loser = (
                (first, second)
                if first.total_score > second.total_score
                else (second, first)
            )
            outcome = Outcome(
                status="WIN",
                winner_school_code=winner.school.school_code,
                loser_school_code=loser.school.school_code,
            )
        result = ComparisonResult(
            date=scored.request.date,
            schools=scored.schools,
            outcome=outcome,
            summary=review.summary,
            school_improvements=review.school_improvements,
            quality_warnings=review.quality_warnings,
        )
        await ctx.yield_output(result.model_dump_json(by_alias=True))


class StorePreparedComparison(Executor):
    def __init__(self) -> None:
        super().__init__(id="dispatch_to_experts")

    @handler
    async def dispatch(
        self,
        prepared: PreparedComparison,
        ctx: WorkflowContext[PreparedComparison],
    ) -> None:
        ctx.set_state("prepared_comparison", prepared)
        await ctx.send_message(prepared)


def create_workflow(
    *,
    settings: Settings,
    gateway: MealGateway | None = None,
    today: Callable[[], date],
    runners: Mapping[str, AgentRunner] | None = None,
) -> Workflow:
    resolved_gateway = gateway or McpGateway(
        str(settings.mcp_url),
        timeout=settings.mcp_timeout,
    )
    resolved_runners = (
        runners if runners is not None else create_copilot_runners(settings)
    )

    prepare = PrepareComparison(resolved_gateway, today)
    dispatcher = StorePreparedComparison()
    experts = [
        ExpertEvaluator(area=area, runner=resolved_runners[area])
        for area in _AREA_WEIGHTS
    ]
    aggregator = ScoreAggregator()
    reviewer = FinalQualityReviewer(resolved_runners["final_reviewer"])
    formatter = ResultFormatter()

    return (
        WorkflowBuilder(start_executor=prepare)
        .add_edge(prepare, dispatcher)
        .add_fan_out_edges(dispatcher, experts)
        .add_fan_in_edges(experts, aggregator)
        .add_edge(aggregator, reviewer)
        .add_edge(reviewer, formatter)
        .build()
    )


def create_copilot_runners(
    settings: Settings,
) -> dict[str, GitHubCopilotAgent]:
    options = GitHubCopilotOptions(**settings.copilot_options())
    runners: dict[str, AgentRunner] = {}
    for area in _AREA_WEIGHTS:
        runners[area] = GitHubCopilotAgent(
            name=f"{area}_agent",
            description=f"{_AREA_LABELS[area]} 평가 전문가",
            instructions=(
                "입력된 NEIS 급식 데이터와 제공된 평가 루브릭만 사용합니다. "
                "확인할 수 없는 수치, 재료, 조리법, 신선도, 선호도 또는 실제 "
                "섭취량을 사실처럼 추정하지 않습니다. 반드시 요청된 JSON만 "
                "반환합니다."
            ),
            default_options=options,
        )
    runners["final_reviewer"] = GitHubCopilotAgent(
        name="final_reviewer_agent",
        description="평가 근거와 최종 설명을 검증하는 품질 평가자",
        instructions=(
            "세 전문 평가의 근거, 모순 및 과도한 추정을 검토합니다. "
            "애플리케이션이 계산한 점수와 승패를 변경하거나 새 점수를 만들지 "
            "않습니다. 반드시 요청된 JSON만 반환합니다."
        ),
        default_options=options,
    )
    return runners


def _expert_prompt(area: AreaName, prepared: PreparedComparison) -> str:
    criteria = {
        "nutrition_balance": (
            "열량과 NEIS 영양정보, 확인 가능한 주식·국/찌개·주찬·부찬·"
            "채소·과일/유제품 식품군 구성을 함께 평가한다."
        ),
        "healthiness": (
            "수치가 있으면 나트륨·당류·지방을 우선 사용한다. 수치가 없으면 "
            "메뉴명에서 직접 확인되는 튀김·가공육·고당 후식 신호만 제한적으로 "
            "사용하고 추정임을 표시한다."
        ),
        "ingredient_quality": (
            "메뉴와 원산지에서 확인되는 식재료 다양성, 메뉴 조화, 중복 여부와 "
            "한 끼 완성도를 평가한다. 신선도와 학생 선호도는 단정하지 않는다."
        ),
    }[area]
    payload = prepared.model_dump(mode="json", by_alias=True)
    return (
        f"평가 영역: {_AREA_LABELS[area]} ({_AREA_WEIGHTS[area]}%)\n"
        f"기준: {criteria}\n"
        "각 학교를 1~5점으로 평가하세요. 모든 핵심 주장에는 입력 데이터에서 "
        "직접 확인 가능한 근거를 붙이세요. 두 학교 모두 개선안을 제시하세요.\n"
        "다음 JSON 형식만 반환하세요:\n"
        '{"area":"'
        f'{area}'
        '","schools":[{"schoolCode":"학교코드","score":1,'
        '"rationale":"평가 이유","evidence":["근거"],'
        '"improvements":["개선안"]}]}\n'
        f"사용자 요청: {prepared.request.prompt}\n"
        f"입력 데이터: {json.dumps(payload, ensure_ascii=False)}"
    )


def _review_prompt(scored: ScoredComparison) -> str:
    payload = scored.model_dump(mode="json", by_alias=True)
    return (
        "최종 품질 게이트를 수행하세요. 세 전문 평가가 각 영역의 1~5점 기준을 "
        "사용했는지, 모든 핵심 주장에 입력 급식 데이터 근거가 있는지, 평가 간 "
        "모순·근거 부족·과도한 추정이 있는지 확인하세요. 입력의 totalScore와 "
        "weightedScore는 애플리케이션 계산값이므로 수정하거나 다시 계산하지 "
        "마세요. 승자 또는 동점의 핵심 이유와 양쪽 학교의 실행 가능한 개선안을 "
        "한국어로 작성하세요.\n"
        "다음 JSON 형식만 반환하세요:\n"
        '{"summary":"총평","schoolImprovements":{"학교코드":["개선안"]},'
        '"qualityWarnings":["품질 경고"]}\n'
        f"평가 및 계산 결과: {json.dumps(payload, ensure_ascii=False)}"
    )


def _json_text(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```") and stripped.endswith("```"):
        lines = stripped.splitlines()
        return "\n".join(lines[1:-1]).strip()
    return stripped

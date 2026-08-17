# 급식 비교 멀티 에이전트

기존 FastAPI 백엔드와 분리된 Python 서비스입니다. Microsoft Agent Framework의
fan-out/fan-in 그래프에서 GitHub Copilot SDK 기반 전문 Agent 세 개를 병렬
실행하고, 애플리케이션 코드로 가중 점수를 계산한 뒤 최종 품질 검증 Agent를
실행합니다.

## 실행

GitHub Copilot CLI에 로그인되어 있어야 하며 트래픽을 생성하는 사용자는
GitHub Copilot 구독이 필요합니다.

```sh
uv sync --locked --all-groups
uv run uvicorn app.main:app --reload --port 8002
```

기본 모델은 계정에서 사용 가능한 모델을 선택하는 `auto`이며 `COPILOT_MODEL`로
변경할 수 있습니다. 컨테이너처럼
로그인 세션을 사용할 수 없는 환경에서는 `GITHUB_TOKEN`을 주입합니다.

- 학교 후보: `GET /schools`
- AG-UI 워크플로우: `POST /ag-ui`
- 상태 확인: `GET /health`

MCP 서버는 기본적으로 `http://127.0.0.1:8001/mcp`를 사용하며 `MCP_URL`로
변경할 수 있습니다.

## DevUI

DevUI는 개발·디버깅 전용이며 프로덕션 UI로 사용하지 않습니다.

```sh
uv run python -m app.devui
```

<http://127.0.0.1:8003>에서 워크플로우 단계와 출력을 확인할 수 있습니다.

# NEIS MCP 서버

`data/openapi.json`의 NEIS 학교기본정보 및 급식식단정보 계약을 공식 Python
MCP SDK 1.x 도구로 제공하는 독립 서버입니다. 전송 방식은 Streamable HTTP이며
엔드포인트는 `/mcp`입니다.

## 실행

웹·API·MCP 전체를 로컬 개발 모드로 실행하려면 저장소 루트에서 실행합니다.

```sh
./run_app.sh
```

MCP 서버만 실행하려면 다음 명령을 사용합니다.

```sh
cd src/mcp
uv sync --locked --all-groups
uv run uvicorn app.main:app --host 127.0.0.1 --port 8001
```

- MCP: <http://127.0.0.1:8001/mcp>
- 상태 확인: <http://127.0.0.1:8001/health>

`NEIS_API_KEY`를 설정하지 않으면 조회 결과가 제한되는 NEIS `sample` 키를
사용합니다. `NEIS_BASE_URL`, `NEIS_CONNECT_TIMEOUT`, `NEIS_READ_TIMEOUT`으로
외부 연결 설정을 재정의할 수 있습니다. API 키는 도구 입력이나 응답에
노출되지 않습니다.

MCP Inspector는 별도 터미널에서 실행합니다.

```sh
npx -y @modelcontextprotocol/inspector
```

Inspector에서 `Streamable HTTP`를 선택하고
`http://127.0.0.1:8001/mcp`에 연결합니다.

> `localhost`가 IPv6 `::1`로 해석되면 IPv4에 바인딩된 로컬 MCP 서버에
> 연결하지 못할 수 있습니다. Inspector에는 반드시
> `http://127.0.0.1:8001/mcp`를 입력하세요.

배포와 유사한 컨테이너 실행은 저장소 루트에서
`docker compose up --build`를 사용하며 MCP URL은 동일합니다.

## 도구

| 도구 | 설명 |
|------|------|
| `getSchoolInfo` | 학교 이름 일부 등으로 후보 학교와 교육청·학교 식별 정보를 조회 |
| `getMealServiceDietInfo` | 교육청 코드, 학교 코드 및 날짜 조건으로 중식 급식 정보를 조회 |

도구 이름, 설명 및 입력 스키마는 `data/openapi.json`에서 생성됩니다.
`MMEAL_SC_CODE`는 중식 코드 `2`로 강제되고 인증키와 JSON 응답 형식은
서버가 주입합니다. `INFO-200`은 정상적인 빈 결과로 반환하며 입력 검증,
NEIS 오류, 연결 실패, 잘못된 응답 및 타임아웃은 MCP tool error로 반환합니다.

## 테스트

```sh
cd src/mcp
uv run --locked pytest
```

테스트는 NEIS HTTP 호출을 모킹하며 실제 API 키나 외부 네트워크를 사용하지
않습니다.

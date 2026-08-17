# 급식배틀에 기여하기

프로젝트에 기여해 주셔서 감사합니다. 이슈 또는 Pull Request를 제출하기
전에 이 안내서를 읽어 주세요.

## 행동 강령

이 프로젝트는 [Contributor Covenant 행동 강령](CODE_OF_CONDUCT.md)을
준수합니다. 프로젝트에 참여하면 이 행동 강령을 지키는 데 동의하는 것으로
간주합니다.

## 시작하기

루트의 `.env.example`을 `.env`로 복사하고 로컬에서 발급받은
`NEIS_API_KEY`를 설정합니다. `.env`와 실제 인증키는 커밋하지 않습니다.

```sh
cp .env.example .env
```

1. 리포지토리를 포크합니다.
2. 포크한 리포지토리를 복제합니다.
3. `feat/`, `fix/`, `docs/` 중 하나를 사용해 브랜치를 생성합니다.
4. 변경할 구성 요소의 의존성을 설치합니다.
5. 코드를 변경하고 테스트를 추가하거나 수정합니다.
6. 관련 검사를 로컬에서 실행합니다.

프론트엔드 설정 및 검사:

```sh
cd src/web
npm ci
npm run build
npm test
```

백엔드 설정 및 검사:

```sh
cd src/api
uv sync --locked --all-groups
uv run pytest
```

백엔드 개발 서버 실행:

```sh
cd src/api
uv run uvicorn app.main:app --reload
```

MCP 서버 설정, 검사 및 실행:

```sh
cd src/mcp
uv sync --locked --all-groups
uv run --locked pytest
uv run uvicorn app.main:app --reload --port 8001
```

전체 애플리케이션 로컬 개발 실행:

```sh
./run_app.sh
```

스크립트는 웹 `5173`, API `8000`, MCP `8001` 포트를 사용하며 `Ctrl+C` 또는
개별 서비스 종료 시 시작한 프로세스를 모두 정리합니다.

MCP Inspector로 도구 목록과 호출을 확인하려면 별도 터미널에서 실행합니다.

```sh
npx -y @modelcontextprotocol/inspector
```

Inspector에서 `Streamable HTTP`를 선택하고
`http://127.0.0.1:8001/mcp`에 연결합니다. `localhost`가 IPv6로 해석될 수
있으므로 로컬 MCP 연결에는 `127.0.0.1`을 사용합니다.

배포와 유사한 컨테이너 실행:

```sh
docker compose up --build
```

E2E 테스트:

```sh
cd src/e2e
npm ci
npx playwright install chromium
npm test
```

## Pull Request 절차

1. 각 Pull Request는 하나의 변경 사항에 집중합니다.
2. 동작 또는 설정이 바뀌면 관련 문서를 수정합니다.
3. 버그 수정과 새로운 기능에 대한 테스트를 추가합니다.
4. 모든 CI 검사가 통과하는지 확인합니다.
5. `Closes #123` 형식으로 관련 이슈를 연결합니다.

## 커밋 규칙

[Conventional Commits](https://www.conventionalcommits.org/) 규칙을
사용합니다.

- `feat:` 새로운 기능
- `fix:` 버그 수정
- `docs:` 문서 변경
- `test:` 테스트 추가 또는 변경
- `refactor:` 동작 변경이 없는 코드 구조 개선
- `chore:` 유지 관리 및 의존성 변경

## 버그 신고 및 기능 제안

`.github/ISSUE_TEMPLATE/`에 있는 구조화된 양식을 사용해 주세요. 보안
취약점은 공개적으로 신고하지 말고 [SECURITY.md](SECURITY.md)의 안내를
따라 주세요.

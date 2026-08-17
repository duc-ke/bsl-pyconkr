import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../src/App";
import { server } from "./server";

type User = ReturnType<typeof userEvent.setup>;

function renderApp() {
  const client = new QueryClient({
    defaultOptions: { mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <App />
    </QueryClientProvider>,
  );
}

async function selectDefaultSchool(user: User) {
  await user.type(screen.getByLabelText("학교 이름"), "서울");
  await user.click(await screen.findByRole("button", { name: /서울고등학교/ }));
}

describe("school lunch flow", () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.setSystemTime(new Date("2026-08-17T03:00:00Z"));
  });

  it("searches, selects a school, and displays lunch results", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderApp();

    await selectDefaultSchool(user);

    expect(screen.getAllByText(/2026년 8월 11일/)).not.toHaveLength(0);
    expect(screen.getAllByText(/2026년 8월 17일/)).not.toHaveLength(0);

    await user.click(screen.getByRole("button", { name: "급식 조회하기" }));

    expect(await screen.findByText("현미밥")).toBeInTheDocument();
    expect(screen.getByText("742.3 kcal")).toBeInTheDocument();
    expect(screen.getByText("520명")).toBeInTheDocument();
  });

  it("does not send a search shorter than two trimmed characters", async () => {
    let requestCount = 0;
    server.use(
      http.get("/api/v1/schools", () => {
        requestCount += 1;
        return HttpResponse.json({ items: [] });
      }),
    );
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderApp();

    await user.type(screen.getByLabelText("학교 이름"), " 가 ");
    await vi.advanceTimersByTimeAsync(400);

    expect(
      screen.getByText("학교 이름을 2자 이상 입력해 주세요."),
    ).toBeInTheDocument();
    expect(requestCount).toBe(0);
  });

  it("distinguishes an empty school result", async () => {
    server.use(
      http.get("/api/v1/schools", () =>
        HttpResponse.json({
          items: [],
          pagination: { page: 1, pageSize: 20, totalCount: 0 },
        }),
      ),
    );
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderApp();

    await user.type(screen.getByLabelText("학교 이름"), "없는학교");

    expect(await screen.findByText("검색 결과가 없어요.")).toBeInTheDocument();
  });

  it("retries a failed school search", async () => {
    let requestCount = 0;
    server.use(
      http.get("/api/v1/schools", () => {
        requestCount += 1;
        if (requestCount === 1) {
          return HttpResponse.json(
            {
              type: "https://bsl.example/problems/neis-unavailable",
              title: "외부 서비스를 사용할 수 없음",
              status: 503,
              detail: "NEIS에 연결할 수 없습니다.",
              instance: "/api/v1/schools",
              code: "NEIS_UNAVAILABLE",
              traceId: "test-trace",
            },
            {
              status: 503,
              headers: { "Content-Type": "application/problem+json" },
            },
          );
        }
        return HttpResponse.json({
          items: [
            {
              educationOfficeCode: "B10",
              educationOfficeName: "서울특별시교육청",
              schoolCode: "7010569",
              name: "서울고등학교",
              schoolType: "고등학교",
              region: "서울특별시",
              address: "서울특별시 서초구 효령로 197",
            },
          ],
          pagination: { page: 1, pageSize: 20, totalCount: 1 },
        });
      }),
    );
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderApp();

    await user.type(screen.getByLabelText("학교 이름"), "서울");
    expect(await screen.findByText("학교 검색에 실패했어요.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "다시 시도" }));

    expect(
      await screen.findByRole("button", { name: /서울고등학교/ }),
    ).toBeInTheDocument();
  });

  it("clears an incomplete date range and disables meal lookup", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderApp();
    await selectDefaultSchool(user);

    await user.click(screen.getByRole("button", { name: /2026년 8월 11일/ }));
    await user.click(screen.getByRole("button", { name: "선택 초기화" }));

    expect(
      screen.getByText("시작일과 종료일을 모두 선택해 주세요."),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "급식 조회하기" })).toBeDisabled();
  });

  it("distinguishes no meals and explains changed criteria", async () => {
    server.use(
      http.get("/api/v1/meals", ({ request }) => {
        const url = new URL(request.url);
        return HttpResponse.json({
          school: {
            educationOfficeCode: "B10",
            schoolCode: "7010569",
            name: "서울고등학교",
          },
          range: {
            from: url.searchParams.get("from"),
            to: url.searchParams.get("to"),
          },
          mealType: "LUNCH",
          items: [],
        });
      }),
    );
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderApp();
    await selectDefaultSchool(user);
    await user.click(screen.getByRole("button", { name: "급식 조회하기" }));

    expect(await screen.findByText("등록된 중식이 없어요.")).toBeInTheDocument();
    await user.clear(screen.getByLabelText("학교 이름"));
    await user.type(screen.getByLabelText("학교 이름"), "부산");

    expect(
      screen.getByText(
        "조회 조건이 변경되었습니다. 변경한 조건으로 다시 조회해 주세요.",
      ),
    ).toBeInTheDocument();
  });

  it("shows a fallback when a meal has no menu details", async () => {
    server.use(
      http.get("/api/v1/meals", ({ request }) => {
        const url = new URL(request.url);
        return HttpResponse.json({
          school: {
            educationOfficeCode: "B10",
            schoolCode: "7010569",
            name: "서울고등학교",
          },
          range: {
            from: url.searchParams.get("from"),
            to: url.searchParams.get("to"),
          },
          mealType: "LUNCH",
          items: [
            {
              date: url.searchParams.get("to"),
              dishes: [],
              calorie: null,
              nutrition: [],
              originInfo: [],
              servingCount: null,
            },
          ],
        });
      }),
    );
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderApp();
    await selectDefaultSchool(user);
    await user.click(screen.getByRole("button", { name: "급식 조회하기" }));

    expect(await screen.findByText("메뉴 정보 없음")).toBeInTheDocument();
  });
});

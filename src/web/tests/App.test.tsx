import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../src/App";
import { server } from "./server";

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

describe("school lunch flow", () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.setSystemTime(new Date("2026-08-17T03:00:00Z"));
  });

  it("searches, selects a school, and displays lunch results", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderApp();

    await user.type(screen.getByLabelText("학교 이름"), "서울");
    await user.click(screen.getByRole("button", { name: "검색" }));
    await user.click(await screen.findByRole("button", { name: /서울고등학교/ }));

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
    await user.click(screen.getByRole("button", { name: "검색" }));

    expect(
      screen.getByText("학교 이름을 2자 이상 100자 이하로 입력해 주세요."),
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
    await user.click(screen.getByRole("button", { name: "검색" }));

    expect(await screen.findByText("검색 결과가 없어요.")).toBeInTheDocument();
  });
});

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../src/App";
import {
  getAgentSchools,
  runComparison,
  type ComparisonResult,
} from "../src/api/agent";

vi.mock("../src/api/agent", async (importOriginal) => {
  const original = await importOriginal<typeof import("../src/api/agent")>();
  return {
    ...original,
    getAgentSchools: vi.fn(),
    runComparison: vi.fn(),
  };
});

const schools = Array.from({ length: 10 }, (_, index) => ({
  educationOfficeCode: "B10",
  schoolCode: String(7010000 + index),
  name: `테스트학교 ${index + 1}`,
  schoolType: "고등학교",
  region: "서울특별시",
}));

const result: ComparisonResult = {
  date: "2026-08-17",
  schools: schools.slice(0, 2).map((school, index) => ({
    school,
    totalScore: index === 0 ? 89 : 71,
    areas: [
      {
        area: "nutrition_balance",
        weight: 45,
        rating: index === 0 ? 5 : 4,
        weightedScore: index === 0 ? 45 : 36,
        rationale: "영양정보와 식품군을 근거로 평가했습니다.",
        evidence: ["단백질 35.1g"],
        improvements: ["채소 반찬 보강"],
      },
      {
        area: "healthiness",
        weight: 30,
        rating: 4,
        weightedScore: 24,
        rationale: "확인 가능한 건강 부담 신호를 평가했습니다.",
        evidence: ["입력 영양정보"],
        improvements: ["나트륨 관리"],
      },
      {
        area: "ingredient_quality",
        weight: 25,
        rating: index === 0 ? 4 : 3,
        weightedScore: index === 0 ? 20 : 15,
        rationale: "메뉴 구성과 원산지를 평가했습니다.",
        evidence: ["쌀 국내산"],
        improvements: ["식재료 다양성 보강"],
      },
    ],
  })),
  outcome: {
    status: "WIN",
    winnerSchoolCode: schools[0].schoolCode,
    loserSchoolCode: schools[1].schoolCode,
  },
  summary: "테스트학교 1이 총점에서 앞섭니다.",
  schoolImprovements: {
    [schools[0].schoolCode]: ["채소 반찬을 보강하세요."],
    [schools[1].schoolCode]: ["나트륨 부담을 줄이세요."],
  },
  qualityWarnings: [],
  disclaimer: "이 분석은 영양사의 전문 진단을 대체하지 않습니다.",
};

function renderApp() {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return render(
    <QueryClientProvider client={client}>
      <App />
    </QueryClientProvider>,
  );
}

describe("school lunch analysis flow", () => {
  beforeEach(() => {
    window.history.replaceState({}, "", "/");
    vi.mocked(getAgentSchools).mockResolvedValue(schools);
    vi.mocked(runComparison).mockImplementation(async (_request, onStep) => {
      onStep("nutrition_balance_expert", "running");
      onStep("nutrition_balance_expert", "completed");
      onStep("score_aggregator", "running");
      onStep("score_aggregator", "completed");
      return result;
    });
  });

  it("selects exactly two schools, edits a prompt, and renders scores", async () => {
    const user = userEvent.setup();
    renderApp();

    await user.click(screen.getByRole("button", { name: "급식 분석" }));
    const checkboxes = await screen.findAllByRole("checkbox");
    await user.click(checkboxes[0]);
    await user.click(checkboxes[1]);

    expect(screen.getByText("2/2개 선택됨")).toBeInTheDocument();
    expect(checkboxes[2]).toBeDisabled();

    expect(screen.getByLabelText("급식 날짜")).toHaveTextContent(
      "2026년 8월 17일",
    );
    const prompt = screen.getByLabelText("분석 프롬프트");
    expect((prompt as HTMLTextAreaElement).value).toContain("테스트학교 1");
    await user.type(prompt, " 핵심만 설명해 주세요.");
    await user.click(screen.getByRole("button", { name: "급식 비교 분석하기" }));

    expect(await screen.findByText("테스트학교 1 승리")).toBeInTheDocument();
    expect(screen.getByText("89.0점")).toBeInTheDocument();
    expect(screen.getAllByText("영양 균형")).toHaveLength(2);
    expect(screen.getAllByText("완료")).toHaveLength(2);
    expect(runComparison).toHaveBeenCalledWith(
      expect.objectContaining({
        schools: schools.slice(0, 2),
        date: "2026-08-17",
        prompt: expect.stringContaining("핵심만"),
      }),
      expect.any(Function),
    );
  });
});

import { HttpAgent } from "@ag-ui/client";

export type AgentSchool = {
  educationOfficeCode: string;
  schoolCode: string;
  name: string;
  schoolType?: string | null;
  region?: string | null;
};

export type AreaName =
  | "nutrition_balance"
  | "healthiness"
  | "ingredient_quality";

export type WeightedAreaResult = {
  area: AreaName;
  weight: number;
  rating: number;
  weightedScore: number;
  rationale: string;
  evidence: string[];
  improvements: string[];
};

export type SchoolScore = {
  school: AgentSchool;
  areas: WeightedAreaResult[];
  totalScore: number;
};

export type ComparisonResult = {
  date: string;
  schools: SchoolScore[];
  outcome: {
    status: "WIN" | "TIE";
    winnerSchoolCode?: string | null;
    loserSchoolCode?: string | null;
  };
  summary: string;
  schoolImprovements: Record<string, string[]>;
  qualityWarnings: string[];
  disclaimer: string;
};

export type ComparisonRequest = {
  schools: AgentSchool[];
  date: string;
  prompt: string;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isAgentSchool(value: unknown): value is AgentSchool {
  return (
    isRecord(value) &&
    typeof value.educationOfficeCode === "string" &&
    typeof value.schoolCode === "string" &&
    typeof value.name === "string"
  );
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === "string");
}

function isArea(value: unknown): value is WeightedAreaResult {
  return (
    isRecord(value) &&
    ["nutrition_balance", "healthiness", "ingredient_quality"].includes(
      String(value.area),
    ) &&
    typeof value.weight === "number" &&
    typeof value.rating === "number" &&
    typeof value.weightedScore === "number" &&
    typeof value.rationale === "string" &&
    isStringArray(value.evidence) &&
    isStringArray(value.improvements)
  );
}

function parseComparisonResult(value: unknown): ComparisonResult {
  if (
    !isRecord(value) ||
    typeof value.date !== "string" ||
    typeof value.summary !== "string" ||
    typeof value.disclaimer !== "string" ||
    !Array.isArray(value.schools) ||
    value.schools.length !== 2 ||
    !isRecord(value.outcome) ||
    !["WIN", "TIE"].includes(String(value.outcome.status)) ||
    !isRecord(value.schoolImprovements) ||
    !isStringArray(value.qualityWarnings)
  ) {
    throw new Error("에이전트가 올바른 분석 결과를 반환하지 않았습니다.");
  }
  const schools = value.schools.map((item) => {
    if (
      !isRecord(item) ||
      !isAgentSchool(item.school) ||
      !Array.isArray(item.areas) ||
      item.areas.length !== 3 ||
      !item.areas.every(isArea) ||
      typeof item.totalScore !== "number"
    ) {
      throw new Error("학교별 분석 결과 형식이 올바르지 않습니다.");
    }
    return {
      school: item.school,
      areas: item.areas,
      totalScore: item.totalScore,
    };
  });
  const improvements = Object.fromEntries(
    Object.entries(value.schoolImprovements).map(([schoolCode, items]) => {
      if (!isStringArray(items)) {
        throw new Error("학교별 개선안 형식이 올바르지 않습니다.");
      }
      return [schoolCode, items];
    }),
  );

  return {
    date: value.date,
    schools,
    outcome: {
      status: value.outcome.status as "WIN" | "TIE",
      winnerSchoolCode:
        typeof value.outcome.winnerSchoolCode === "string"
          ? value.outcome.winnerSchoolCode
          : null,
      loserSchoolCode:
        typeof value.outcome.loserSchoolCode === "string"
          ? value.outcome.loserSchoolCode
          : null,
    },
    summary: value.summary,
    schoolImprovements: improvements,
    qualityWarnings: value.qualityWarnings,
    disclaimer: value.disclaimer,
  };
}

export async function getAgentSchools(): Promise<AgentSchool[]> {
  const response = await fetch("/agent/schools", {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error("학교 후보를 불러오지 못했습니다.");
  }
  const value: unknown = await response.json();
  if (!Array.isArray(value) || !value.every(isAgentSchool)) {
    throw new Error("학교 후보 응답 형식이 올바르지 않습니다.");
  }
  return value;
}

export async function runComparison(
  request: ComparisonRequest,
  onStep: (stepName: string, status: "running" | "completed") => void,
): Promise<ComparisonResult> {
  const agent = new HttpAgent({
    url: "/agent/ag-ui",
    threadId: crypto.randomUUID(),
    initialMessages: [
      {
        id: crypto.randomUUID(),
        role: "user",
        content: JSON.stringify(request),
      },
    ],
  });
  let finalText = "";
  let runError: string | undefined;

  try {
    await agent.runAgent(
      {},
      {
        onStepStartedEvent: ({ event }) => {
          onStep(event.stepName, "running");
        },
        onStepFinishedEvent: ({ event }) => {
          onStep(event.stepName, "completed");
        },
        onTextMessageEndEvent: ({ textMessageBuffer }) => {
          finalText = textMessageBuffer;
        },
        onRunErrorEvent: ({ event }) => {
          runError = event.message;
        },
      },
    );
  } catch (error) {
    if (runError) {
      throw new Error(formatRunError(runError));
    }
    throw error;
  }

  if (runError) {
    throw new Error(formatRunError(runError));
  }
  if (!finalText) {
    throw new Error("에이전트 분석 결과를 받지 못했습니다.");
  }
  try {
    return parseComparisonResult(JSON.parse(finalText) as unknown);
  } catch (error) {
    if (error instanceof SyntaxError) {
      throw new Error("에이전트 분석 결과를 해석하지 못했습니다.");
    }
    throw error;
  }
}

function formatRunError(message: string): string {
  if (message.includes("authentication")) {
    return "GitHub Copilot 인증을 확인하지 못했습니다. GitHub CLI 로그인 또는 GITHUB_TOKEN 설정을 확인해 주세요.";
  }
  return message;
}

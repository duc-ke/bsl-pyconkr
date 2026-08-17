import type { components } from "./schema";

export type School = components["schemas"]["SchoolSummary"];
export type SchoolSearchResponse =
  components["schemas"]["SchoolSearchResponse"];
export type MealSearchResponse =
  components["schemas"]["MealSearchResponse"];
export type ProblemDetails = components["schemas"]["ProblemDetails"];

export class ApiError extends Error {
  constructor(public readonly problem: ProblemDetails) {
    super(problem.detail);
    this.name = "ApiError";
  }
}

async function request<T>(path: string): Promise<T> {
  const response = await fetch(path, {
    headers: { Accept: "application/json, application/problem+json" },
  });

  if (!response.ok) {
    const contentType = response.headers.get("content-type") ?? "";
    if (contentType.includes("application/problem+json")) {
      throw new ApiError((await response.json()) as ProblemDetails);
    }
    throw new Error("서버 응답을 처리할 수 없습니다. 잠시 후 다시 시도해 주세요.");
  }

  return (await response.json()) as T;
}

export function searchSchools(query: string): Promise<SchoolSearchResponse> {
  const params = new URLSearchParams({
    query,
    page: "1",
    pageSize: "20",
  });
  return request(`/api/v1/schools?${params}`);
}

export function searchMeals(
  school: School,
  from: string,
  to: string,
): Promise<MealSearchResponse> {
  const params = new URLSearchParams({
    educationOfficeCode: school.educationOfficeCode,
    schoolCode: school.schoolCode,
    from,
    to,
  });
  return request(`/api/v1/meals?${params}`);
}

export function getErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.problem.detail;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "요청을 완료하지 못했습니다. 잠시 후 다시 시도해 주세요.";
}

import { expect, test } from "@playwright/test";

function koreanDateInSeoul(offsetDays: number): string {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Seoul",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts();
  const values = Object.fromEntries(
    parts.map(({ type, value }) => [type, value]),
  );
  const date = new Date(
    Date.UTC(Number(values.year), Number(values.month) - 1, Number(values.day)),
  );
  date.setUTCDate(date.getUTCDate() + offsetDays);
  return `${date.getUTCFullYear()}년 ${date.getUTCMonth() + 1}월 ${date.getUTCDate()}일`;
}

test("학교 검색부터 중식 결과까지 조회한다", async ({ page }) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "급식 배틀 - 학교 급식 조회 앱" }),
  ).toBeVisible();

  await page.getByLabel("학교 이름").fill("서울");
  await page.getByRole("button", { name: /서울고등학교/ }).click();

  await expect(page.getByText("서울고등학교 · 중식")).toBeVisible();
  await page.getByRole("button", { name: "급식 조회하기" }).click();

  await expect(page.getByRole("heading", { name: "서울고등학교의 중식" })).toBeVisible();
  await expect(page.getByText("현미밥")).toBeVisible();
  await expect(page.getByText("742.3 kcal")).toBeVisible();
});

test("급식이 없는 상태를 정상 빈 결과로 표시한다", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("학교 이름").fill("빈급식학교");
  await page.getByRole("button", { name: /빈급식학교/ }).click();
  await page.getByRole("button", { name: "급식 조회하기" }).click();

  await expect(page.getByText("등록된 중식이 없어요.")).toBeVisible();
});

test("NEIS 장애를 검색 결과 없음과 구분한다", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("학교 이름").fill("오류학교");

  await expect(page.getByText("학교 검색에 실패했어요.")).toBeVisible();
  await expect(page.getByRole("button", { name: "다시 시도" })).toBeVisible();
});

test("키보드만으로 학교 선택과 급식 조회를 완료한다", async ({ page }) => {
  await page.goto("/");
  const input = page.getByLabel("학교 이름");
  await input.focus();
  await page.keyboard.type("서울");

  const school = page.getByRole("button", { name: /서울고등학교/ });
  await expect(school).toBeVisible();
  await page.keyboard.press("Tab");
  await expect(school).toBeFocused();
  await page.keyboard.press("Enter");

  await page.keyboard.press("Tab");
  await page.keyboard.press("Tab");
  const dateTrigger = page.locator(".date-trigger");
  await expect(dateTrigger).toBeFocused();
  await expect(dateTrigger).toContainText(koreanDateInSeoul(-6));
  await expect(dateTrigger).toContainText(koreanDateInSeoul(0));
  await page.keyboard.press("Enter");
  await expect(page.getByRole("dialog", { name: "날짜 범위 선택" })).toBeVisible();
  await page.keyboard.press("Escape");

  await page.keyboard.press("Tab");
  const mealButton = page.getByRole("button", { name: "급식 조회하기" });
  await expect(mealButton).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.getByText("현미밥")).toBeVisible();
});

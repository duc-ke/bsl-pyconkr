import { expect, test } from "@playwright/test";

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

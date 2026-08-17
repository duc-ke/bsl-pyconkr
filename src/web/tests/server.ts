import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";

export const school = {
  educationOfficeCode: "B10",
  educationOfficeName: "서울특별시교육청",
  schoolCode: "7010569",
  name: "서울고등학교",
  schoolType: "고등학교",
  region: "서울특별시",
  address: "서울특별시 서초구 효령로 197",
};

export const handlers = [
  http.get("/api/v1/schools", () =>
    HttpResponse.json({
      items: [school],
      pagination: { page: 1, pageSize: 20, totalCount: 1 },
    }),
  ),
  http.get("/api/v1/meals", ({ request }) => {
    const url = new URL(request.url);
    return HttpResponse.json({
      school: {
        educationOfficeCode: school.educationOfficeCode,
        schoolCode: school.schoolCode,
        name: school.name,
      },
      range: {
        from: url.searchParams.get("from"),
        to: url.searchParams.get("to"),
      },
      mealType: "LUNCH",
      items: [
        {
          date: url.searchParams.get("to"),
          dishes: ["현미밥", "된장국", "닭갈비"],
          calorie: { amount: 742.3, unit: "kcal" },
          nutrition: [{ name: "단백질", amount: 35.1, unit: "g" }],
          originInfo: [{ ingredient: "쌀", origin: "국내산" }],
          servingCount: 520,
        },
      ],
    });
  }),
];

export const server = setupServer(...handlers);

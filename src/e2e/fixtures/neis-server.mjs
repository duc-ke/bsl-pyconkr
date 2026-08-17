import { createServer } from "node:http";

const school = {
  ATPT_OFCDC_SC_CODE: "B10",
  ATPT_OFCDC_SC_NM: "서울특별시교육청",
  SD_SCHUL_CODE: "7010569",
  SCHUL_NM: "서울고등학교",
  SCHUL_KND_SC_NM: "고등학교",
  LCTN_SC_NM: "서울특별시",
  ORG_RDNMA: "서울특별시 서초구 효령로",
  ORG_RDNDA: "197",
};

function list(resource, rows) {
  return {
    [resource]: [
      {
        head: [
          { list_total_count: rows.length },
          { RESULT: { CODE: "INFO-000", MESSAGE: "정상 처리" } },
        ],
      },
      { row: rows },
    ],
  };
}

createServer((request, response) => {
  const url = new URL(request.url ?? "/", "http://localhost");
  response.setHeader("content-type", "application/json; charset=utf-8");

  if (url.pathname === "/health") {
    response.end(JSON.stringify({ status: "ok" }));
    return;
  }

  if (url.pathname === "/hub/schoolInfo") {
    response.end(JSON.stringify(list("schoolInfo", [school])));
    return;
  }

  if (url.pathname === "/hub/mealServiceDietInfo") {
    const date = url.searchParams.get("MLSV_TO_YMD");
    response.end(
      JSON.stringify(
        list("mealServiceDietInfo", [
          {
            ATPT_OFCDC_SC_CODE: school.ATPT_OFCDC_SC_CODE,
            SD_SCHUL_CODE: school.SD_SCHUL_CODE,
            SCHUL_NM: school.SCHUL_NM,
            MMEAL_SC_CODE: "2",
            MLSV_YMD: date,
            DDISH_NM: "현미밥<br/>된장국<br/>닭갈비",
            CAL_INFO: "742.3 Kcal",
            NTR_INFO: "단백질(g) : 35.1",
            ORPLC_INFO: "쌀 : 국내산",
            MLSV_FGR: 520,
          },
        ]),
      ),
    );
    return;
  }

  response.statusCode = 404;
  response.end(JSON.stringify({ error: "not found" }));
}).listen(9090, "0.0.0.0");

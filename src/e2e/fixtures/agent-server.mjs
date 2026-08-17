import { createServer } from "node:http";
import { randomUUID } from "node:crypto";

const schools = Array.from({ length: 10 }, (_, index) => ({
  educationOfficeCode: "B10",
  schoolCode: String(7010569 + index),
  name: `비교학교 ${index + 1}`,
  schoolType: "고등학교",
  region: "서울특별시",
}));

function sendEvent(response, event) {
  response.write(`data: ${JSON.stringify(event)}\n\n`);
}

createServer((request, response) => {
  const url = new URL(request.url ?? "/", "http://localhost");

  if (url.pathname === "/health") {
    response.setHeader("content-type", "application/json");
    response.end(JSON.stringify({ status: "ok" }));
    return;
  }

  if (url.pathname === "/schools" && request.method === "GET") {
    response.setHeader("content-type", "application/json");
    response.end(JSON.stringify(schools));
    return;
  }

  if (url.pathname === "/ag-ui" && request.method === "POST") {
    let body = "";
    request.on("data", (chunk) => {
      body += chunk;
    });
    request.on("end", () => {
      const input = JSON.parse(body);
      const message = input.messages.at(-1);
      const comparison = JSON.parse(message.content);
      const selected = comparison.schools;
      const result = {
        date: comparison.date,
        schools: selected.map((school, index) => ({
          school,
          areas: [
            {
              area: "nutrition_balance",
              weight: 45,
              rating: index === 0 ? 5 : 4,
              weightedScore: index === 0 ? 45 : 36,
              rationale: "영양정보와 식품군 구성을 근거로 평가했습니다.",
              evidence: ["단백질 35.1g"],
              improvements: ["채소 반찬 보강"],
            },
            {
              area: "healthiness",
              weight: 30,
              rating: 4,
              weightedScore: 24,
              rationale: "확인 가능한 건강 부담 신호를 평가했습니다.",
              evidence: ["NEIS 영양정보"],
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
          totalScore: index === 0 ? 89 : 75,
        })),
        outcome: {
          status: "WIN",
          winnerSchoolCode: selected[0].schoolCode,
          loserSchoolCode: selected[1].schoolCode,
        },
        summary: `${selected[0].name}가 총점에서 앞섭니다.`,
        schoolImprovements: {
          [selected[0].schoolCode]: ["채소 반찬을 보강하세요."],
          [selected[1].schoolCode]: ["나트륨 부담을 줄이세요."],
        },
        qualityWarnings: [],
        disclaimer: "이 분석은 영양사의 전문 진단을 대체하지 않습니다.",
      };
      const threadId = input.threadId ?? randomUUID();
      const runId = input.runId ?? randomUUID();
      const messageId = randomUUID();

      response.writeHead(200, {
        "content-type": "text/event-stream",
        "cache-control": "no-cache",
        connection: "keep-alive",
      });
      sendEvent(response, { type: "RUN_STARTED", threadId, runId });
      for (const stepName of [
        "nutrition_balance_expert",
        "healthiness_expert",
        "ingredient_quality_expert",
        "score_aggregator",
        "final_quality_reviewer",
      ]) {
        sendEvent(response, { type: "STEP_STARTED", stepName });
        sendEvent(response, { type: "STEP_FINISHED", stepName });
      }
      sendEvent(response, {
        type: "TEXT_MESSAGE_START",
        messageId,
        role: "assistant",
      });
      sendEvent(response, {
        type: "TEXT_MESSAGE_CONTENT",
        messageId,
        delta: JSON.stringify(result),
      });
      sendEvent(response, { type: "TEXT_MESSAGE_END", messageId });
      sendEvent(response, { type: "RUN_FINISHED", threadId, runId });
      response.end();
    });
    return;
  }

  response.statusCode = 404;
  response.end(JSON.stringify({ error: "not found" }));
}).listen(8000, "0.0.0.0");

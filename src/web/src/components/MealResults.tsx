import type { MealSearchResponse, School } from "../api/client";
import { formatKoreanDate } from "../utils/dates";
import { parseISO } from "date-fns";

type MealResultsProps = {
  school: School;
  data: MealSearchResponse;
};

export function MealResults({ school, data }: MealResultsProps) {
  return (
    <section className="results-section" aria-labelledby="results-title">
      <div className="results-heading">
        <div>
          <div className="step-label">03 · 급식 결과</div>
          <h2 id="results-title">{school.name}의 중식</h2>
        </div>
        <p>
          {data.range.from} ~ {data.range.to}
        </p>
      </div>
      {data.items.length === 0 ? (
        <div className="empty-state" role="status">
          <strong>등록된 중식이 없어요.</strong>
          <span>선택한 기간을 바꿔 다시 조회해 보세요.</span>
        </div>
      ) : (
        <div className="meal-grid">
          {data.items.map((meal) => (
            <article className="meal-card" key={meal.date}>
              <header>
                <span className="meal-type">중식</span>
                <h3>{formatKoreanDate(parseISO(meal.date))}</h3>
                <p>{school.name}</p>
              </header>
              {meal.dishes.length > 0 ? (
                <ul className="dish-list" aria-label="메뉴">
                  {meal.dishes.map((dish, index) => (
                    <li key={`${dish}-${index}`}>{dish}</li>
                  ))}
                </ul>
              ) : (
                <p className="dish-empty">메뉴 정보 없음</p>
              )}
              <dl className="meal-meta">
                <div>
                  <dt>열량</dt>
                  <dd>
                    {meal.calorie
                      ? `${meal.calorie.amount} ${meal.calorie.unit}`
                      : "정보 없음"}
                  </dd>
                </div>
                <div>
                  <dt>급식 인원</dt>
                  <dd>
                    {meal.servingCount === null
                      ? "정보 없음"
                      : `${meal.servingCount.toLocaleString("ko-KR")}명`}
                  </dd>
                </div>
              </dl>
              {meal.nutrition.length > 0 && (
                <details>
                  <summary>영양 정보</summary>
                  <dl className="detail-list">
                    {meal.nutrition.map((item) => (
                      <div key={item.name}>
                        <dt>{item.name}</dt>
                        <dd>{item.amount} {item.unit}</dd>
                      </div>
                    ))}
                  </dl>
                </details>
              )}
              {meal.originInfo.length > 0 && (
                <details>
                  <summary>원산지 정보</summary>
                  <dl className="detail-list">
                    {meal.originInfo.map((item) => (
                      <div key={`${item.ingredient}-${item.origin}`}>
                        <dt>{item.ingredient}</dt>
                        <dd>{item.origin}</dd>
                      </div>
                    ))}
                  </dl>
                </details>
              )}
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

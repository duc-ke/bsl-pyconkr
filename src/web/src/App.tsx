import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import type { DateRange } from "react-day-picker";
import {
  getErrorMessage,
  searchMeals,
  searchSchools,
  type School,
} from "./api/client";
import { DateRangeCard } from "./components/DateRangeCard";
import { MealResults } from "./components/MealResults";
import { getDatePolicy, toApiDate } from "./utils/dates";

export function App() {
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [selectedSchool, setSelectedSchool] = useState<School>();
  const [range, setRange] = useState<DateRange | undefined>(
    getDatePolicy().initial,
  );

  const normalizedQuery = query.trim();
  const inputError =
    normalizedQuery.length > 0 && normalizedQuery.length < 2
      ? "학교 이름을 2자 이상 입력해 주세요."
      : normalizedQuery.length > 100
        ? "학교 이름을 100자 이하로 입력해 주세요."
        : undefined;

  useEffect(() => {
    if (normalizedQuery.length < 2 || normalizedQuery.length > 100) {
      setDebouncedQuery("");
      return;
    }
    const timer = window.setTimeout(
      () => setDebouncedQuery(normalizedQuery),
      350,
    );
    return () => window.clearTimeout(timer);
  }, [normalizedQuery]);

  const schools = useQuery({
    queryKey: ["schools", debouncedQuery],
    queryFn: () => searchSchools(debouncedQuery),
    enabled: debouncedQuery.length >= 2,
    retry: false,
  });
  const showSchoolState =
    debouncedQuery.length >= 2 && debouncedQuery === normalizedQuery;
  const meals = useMutation({
    mutationFn: ({
      school,
      selectedRange,
    }: {
      school: School;
      selectedRange: { from: Date; to: Date };
    }) =>
      searchMeals(
        school,
        toApiDate(selectedRange.from),
        toApiDate(selectedRange.to),
      ),
  });

  const selectSchool = (school: School) => {
    setSelectedSchool(school);
    meals.reset();
  };

  const changeRange = (nextRange: DateRange | undefined) => {
    setRange(nextRange);
    meals.reset();
  };

  const canSearchMeals =
    selectedSchool && range?.from && range.to && !meals.isPending;

  return (
    <main>
      <header className="hero">
        <a className="brand" href="/" aria-label="급식 배틀 홈">
          <span className="brand-mark" aria-hidden="true">급</span>
          급식 배틀
        </a>
        <div className="hero-copy">
          <p className="eyebrow">오늘의 학교 식탁을 한눈에</p>
          <h1>급식 배틀 - 학교 급식 조회 앱</h1>
          <p>
            학교를 찾고 날짜를 고르면 중식 메뉴와 영양 정보를 깔끔하게
            모아 보여드려요.
          </p>
        </div>
      </header>

      <div className="bento-grid">
        <section className="card search-card">
          <div className="step-label">01 · 학교 찾기</div>
          <h2>어느 학교의 급식인가요?</h2>
          <div>
            <label htmlFor="school-query">학교 이름</label>
            <div className="search-row">
              <input
                id="school-query"
                value={query}
                onChange={(event) => {
                  setQuery(event.target.value);
                  setSelectedSchool(undefined);
                  meals.reset();
                }}
                placeholder="예: 서울고등학교"
                aria-describedby={inputError ? "school-query-error" : undefined}
                aria-invalid={Boolean(inputError)}
              />
            </div>
            {inputError && (
              <p className="field-message" id="school-query-error">
                {inputError}
              </p>
            )}
            {!inputError && normalizedQuery.length >= 2 && (
              <p className="search-hint" aria-live="polite">
                {schools.isFetching ? "학교를 검색하고 있어요…" : "자동으로 검색됩니다."}
              </p>
            )}
          </div>
          <div aria-live="polite">
            {showSchoolState && schools.isError && (
              <div className="error-state" role="alert">
                <strong>학교 검색에 실패했어요.</strong>
                <span>{getErrorMessage(schools.error)}</span>
                <button type="button" onClick={() => schools.refetch()}>
                  다시 시도
                </button>
              </div>
            )}
            {showSchoolState && schools.data?.items.length === 0 && (
              <div className="empty-state" role="status">
                <strong>검색 결과가 없어요.</strong>
                <span>학교 이름을 확인하거나 더 넓은 검색어를 사용해 보세요.</span>
              </div>
            )}
            {showSchoolState && schools.data && schools.data.items.length > 0 && (
              <ul className="school-results" aria-label="학교 검색 결과">
                {schools.data.items.map((school) => {
                  const selected =
                    selectedSchool?.educationOfficeCode ===
                      school.educationOfficeCode &&
                    selectedSchool.schoolCode === school.schoolCode;
                  return (
                    <li key={`${school.educationOfficeCode}-${school.schoolCode}`}>
                      <button
                        type="button"
                        className={selected ? "selected" : ""}
                        aria-pressed={selected}
                        onClick={() => selectSchool(school)}
                      >
                        <span>
                          <strong>{school.name}</strong>
                          <small>{school.region} · {school.schoolType}</small>
                          <small>{school.address ?? "주소 정보 없음"}</small>
                        </span>
                        <span aria-hidden="true">{selected ? "✓" : "→"}</span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </section>

        <section className={`card selected-card ${selectedSchool ? "" : "is-disabled"}`}>
          <div className="step-label">선택한 학교</div>
          {selectedSchool ? (
            <>
              <span className="selection-check" aria-hidden="true">✓</span>
              <h2>{selectedSchool.name}</h2>
              <p>{selectedSchool.educationOfficeName}</p>
              <p>{selectedSchool.address ?? "주소 정보 없음"}</p>
              <button
                className="text-button"
                type="button"
                onClick={() => {
                  setSelectedSchool(undefined);
                  meals.reset();
                }}
              >
                학교 다시 선택
              </button>
            </>
          ) : (
            <>
              <span className="selection-placeholder" aria-hidden="true">⌁</span>
              <h2>학교를 선택해 주세요</h2>
              <p>검색 결과에서 학교를 고르면 날짜를 선택할 수 있어요.</p>
            </>
          )}
        </section>

        <DateRangeCard
          disabled={!selectedSchool}
          range={range}
          onChange={changeRange}
        />

        <section className={`card action-card ${canSearchMeals ? "" : "is-disabled"}`}>
          <div>
            <div className="step-label">준비 완료</div>
            <h2>선택한 기간의 중식을 확인하세요.</h2>
            <p>
              {selectedSchool
                ? `${selectedSchool.name} · 중식`
                : "학교와 날짜 범위를 먼저 선택해 주세요."}
            </p>
          </div>
          <button
            className="primary-action"
            type="button"
            disabled={!canSearchMeals}
            onClick={() => {
              if (selectedSchool && range?.from && range.to) {
                meals.mutate({
                  school: selectedSchool,
                  selectedRange: { from: range.from, to: range.to },
                });
              }
            }}
          >
            {meals.isPending ? "급식 조회 중…" : "급식 조회하기"}
          </button>
        </section>
      </div>

      {meals.isError && (
        <div className="error-state results-error" role="alert">
          <strong>급식 조회에 실패했어요.</strong>
          <span>{getErrorMessage(meals.error)}</span>
          <span>잠시 후 다시 시도해 주세요.</span>
        </div>
      )}
      {selectedSchool && meals.data && (
        <MealResults school={selectedSchool} data={meals.data} />
      )}

      <footer>
        <span>NEIS 공개 데이터를 바탕으로 제공합니다.</span>
        <span>선택 정보는 실제 제공 여부에 따라 달라질 수 있어요.</span>
      </footer>
    </main>
  );
}

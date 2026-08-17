import { useMutation, useQuery } from "@tanstack/react-query";
import { parseISO } from "date-fns";
import { useEffect, useMemo, useRef, useState } from "react";
import { DayPicker } from "react-day-picker";
import { ko } from "react-day-picker/locale";
import {
  getAgentSchools,
  runComparison,
  type AgentSchool,
  type AreaName,
  type ComparisonResult,
} from "../api/agent";
import {
  formatKoreanDate,
  getDatePolicy,
  toApiDate,
} from "../utils/dates";

const AREA_LABELS: Record<AreaName, string> = {
  nutrition_balance: "영양 균형",
  healthiness: "건강성",
  ingredient_quality: "식재료 및 메뉴 품질",
};

const STEP_LABELS: Record<string, string> = {
  prepare_comparison: "MCP에서 중식 데이터를 확인하고 있어요.",
  dispatch_to_experts: "세 전문 평가자에게 데이터를 전달하고 있어요.",
  nutrition_balance_expert: "영양 균형을 평가하고 있어요.",
  healthiness_expert: "건강성을 평가하고 있어요.",
  ingredient_quality_expert: "식재료와 메뉴 품질을 평가하고 있어요.",
  score_aggregator: "가중 점수와 총점을 계산하고 있어요.",
  final_quality_reviewer: "근거와 모순을 최종 검토하고 있어요.",
  result_formatter: "분석 결과를 정리하고 있어요.",
};

type ProgressStep = {
  name: string;
  label: string;
  status: "running" | "completed";
};

function defaultPrompt(schools: AgentSchool[], selectedDate: string): string {
  if (schools.length !== 2 || !selectedDate) return "";
  return `${schools[0].name}와 ${schools[1].name}의 ${selectedDate} 중식을 EVALUATION_RUBRIC.md의 세 평가영역에 따라 비교하고, 근거와 개선안을 한국어로 설명해 주세요.`;
}

export function AnalysisPage() {
  const policy = useMemo(() => getDatePolicy(), []);
  const candidates = useQuery({
    queryKey: ["agent-schools"],
    queryFn: getAgentSchools,
    retry: false,
  });
  const [selectedCodes, setSelectedCodes] = useState<string[]>([]);
  const [selectedDate, setSelectedDate] = useState(() =>
    toApiDate(policy.today)
  );
  const [prompt, setPrompt] = useState("");
  const [progress, setProgress] = useState<ProgressStep[]>([]);
  const selectedSchools =
    candidates.data?.filter((school) =>
      selectedCodes.includes(school.schoolCode),
    ) ?? [];

  useEffect(() => {
    setPrompt(defaultPrompt(selectedSchools, selectedDate));
  }, [selectedCodes.join(","), selectedDate, candidates.data]);

  const analysis = useMutation({
    mutationFn: () =>
      runComparison(
        {
          schools: selectedSchools,
          date: selectedDate,
          prompt,
        },
        (stepName, status) => {
          const label = STEP_LABELS[stepName];
          if (!label) return;
          setProgress((current) => {
            const existing = current.findIndex((step) => step.name === stepName);
            if (existing === -1) {
              return [...current, { name: stepName, label, status }];
            }
            return current.map((step, index) =>
              index === existing ? { ...step, status } : step
            );
          });
        },
      ),
  });

  const toggleSchool = (schoolCode: string) => {
    analysis.reset();
    setProgress([]);
    setSelectedCodes((current) => {
      if (current.includes(schoolCode)) {
        return current.filter((code) => code !== schoolCode);
      }
      if (current.length === 2) return current;
      return [...current, schoolCode];
    });
  };
  const canAnalyze =
    selectedSchools.length === 2 &&
    Boolean(selectedDate) &&
    Boolean(prompt.trim()) &&
    !analysis.isPending;

  return (
    <main>
      <header className="hero analysis-hero">
        <div className="hero-copy">
          <p className="eyebrow">Copilot SDK · Microsoft Agent Framework</p>
          <h1>두 학교의 급식을 근거로 비교해 보세요.</h1>
          <p>
            세 전문 Agent가 독립적으로 평가하고, 애플리케이션이 가중 점수를
            계산한 뒤 최종 평가자가 근거를 검증합니다.
          </p>
        </div>
      </header>

      <div className="analysis-grid">
        <section className="card candidate-card">
          <div className="step-label">01 · 학교 선택</div>
          <h2>무작위 학교 중 정확히 두 곳을 선택하세요.</h2>
          <p className="supporting" aria-live="polite">
            {selectedCodes.length}/2개 선택됨
          </p>
          {candidates.isPending && <p>학교 후보를 불러오고 있어요…</p>}
          {candidates.isError && (
            <div className="error-state" role="alert">
              <strong>학교 후보를 불러오지 못했어요.</strong>
              <button type="button" onClick={() => candidates.refetch()}>
                다시 시도
              </button>
            </div>
          )}
          {candidates.data && (
            <fieldset className="candidate-list">
              <legend className="sr-only">비교할 학교 선택</legend>
              {candidates.data.map((school) => {
                const selected = selectedCodes.includes(school.schoolCode);
                const disabled = !selected && selectedCodes.length === 2;
                return (
                  <label
                    key={`${school.educationOfficeCode}-${school.schoolCode}`}
                    className={selected ? "candidate selected" : "candidate"}
                  >
                    <input
                      type="checkbox"
                      checked={selected}
                      disabled={disabled}
                      onChange={() => toggleSchool(school.schoolCode)}
                    />
                    <span>
                      <strong>{school.name}</strong>
                      <small>
                        {school.region ?? "지역 정보 없음"} ·{" "}
                        {school.schoolType ?? "학교 종류 정보 없음"}
                      </small>
                    </span>
                  </label>
                );
              })}
            </fieldset>
          )}
        </section>

        <section className="card analysis-settings">
          <div className="step-label">02 · 날짜와 요청</div>
          <h2>평가할 하루를 선택하세요.</h2>
          <AnalysisDatePicker
            value={selectedDate}
            onChange={(value) => {
              setSelectedDate(value);
              analysis.reset();
              setProgress([]);
            }}
            policy={policy}
          />
          <label htmlFor="analysis-prompt">분석 프롬프트</label>
          <textarea
            id="analysis-prompt"
            rows={8}
            maxLength={4000}
            value={prompt}
            onChange={(event) => setPrompt(event.target.value)}
            placeholder="학교 두 곳과 날짜를 선택하면 기본 프롬프트가 생성됩니다."
          />
          <button
            className="primary-action"
            type="button"
            disabled={!canAnalyze}
            onClick={() => {
              setProgress([]);
              analysis.mutate();
            }}
          >
            {analysis.isPending ? "멀티 에이전트 분석 중…" : "급식 비교 분석하기"}
          </button>
        </section>
      </div>

      {(analysis.isPending || progress.length > 0) && (
        <section className="progress-panel" aria-live="polite">
          <h2>워크플로우 진행 상태</h2>
          <ol>
            {progress.map((step) => (
              <li className={`progress-step ${step.status}`} key={step.name}>
                <span aria-hidden="true">
                  {step.status === "completed" ? "✓" : "●"}
                </span>
                <span>{step.label}</span>
                <small>
                  {step.status === "completed" ? "완료" : "진행 중"}
                </small>
              </li>
            ))}
          </ol>
        </section>
      )}
      {analysis.isError && (
        <div className="error-state results-error" role="alert">
          <strong>급식 분석에 실패했어요.</strong>
          <span>
            {analysis.error instanceof Error
              ? analysis.error.message
              : "요청을 완료하지 못했습니다."}
          </span>
        </div>
      )}
      {analysis.data && <AnalysisResults result={analysis.data} />}

      <footer>
        <span>NEIS 공개 데이터와 선택 날짜의 중식만 평가에 사용합니다.</span>
        <span>메뉴명만으로 확인할 수 없는 정보는 단정하지 않습니다.</span>
      </footer>
    </main>
  );
}

type DatePolicy = ReturnType<typeof getDatePolicy>;

function AnalysisDatePicker({
  value,
  onChange,
  policy,
}: {
  value: string;
  onChange: (value: string) => void;
  policy: DatePolicy;
}) {
  const [open, setOpen] = useState(false);
  const popoverRef = useRef<HTMLDivElement>(null);
  const selected = value ? parseISO(value) : undefined;

  useEffect(() => {
    if (!open) return;
    const close = (event: MouseEvent) => {
      if (!popoverRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [open]);

  return (
    <>
      <label htmlFor="analysis-date">급식 날짜</label>
      <div className="date-control" ref={popoverRef}>
        <button
          id="analysis-date"
          className="date-trigger"
          type="button"
          aria-expanded={open}
          aria-haspopup="dialog"
          onClick={() => setOpen((current) => !current)}
        >
          <span aria-hidden="true">▦</span>
          <span>
            {selected ? formatKoreanDate(selected) : "급식 날짜를 선택해 주세요."}
          </span>
        </button>
        {open && (
          <div
            className="calendar-popover"
            role="dialog"
            aria-label="급식 날짜 선택"
          >
            <DayPicker
              mode="single"
              locale={ko}
              selected={selected}
              onSelect={(date) => {
                if (!date) return;
                onChange(toApiDate(date));
                setOpen(false);
              }}
              defaultMonth={selected ?? policy.today}
              startMonth={policy.min}
              endMonth={policy.max}
              disabled={{ before: policy.min, after: policy.max }}
              showOutsideDays
            />
          </div>
        )}
      </div>
    </>
  );
}

function AnalysisResults({ result }: { result: ComparisonResult }) {
  const winner =
    result.outcome.status === "WIN"
      ? result.schools.find(
          (school) =>
            school.school.schoolCode === result.outcome.winnerSchoolCode,
        )
      : undefined;

  return (
    <section className="analysis-results" aria-live="polite">
      <div className="results-heading">
        <div>
          <p className="eyebrow">최종 비교 결과</p>
          <h2>
            {winner ? `${winner.school.name} 승리` : "두 학교가 동점입니다"}
          </h2>
        </div>
        <span>{result.date}</span>
      </div>
      <p className="result-summary">{result.summary}</p>
      <div className="score-grid">
        {result.schools.map((schoolResult) => (
          <article className="score-card" key={schoolResult.school.schoolCode}>
            <header>
              <h3>{schoolResult.school.name}</h3>
              <strong>{schoolResult.totalScore.toFixed(1)}점</strong>
            </header>
            {schoolResult.areas.map((area) => (
              <section key={area.area} className="area-result">
                <div>
                  <h4>{AREA_LABELS[area.area]}</h4>
                  <strong>
                    {area.rating}/5 · {area.weightedScore.toFixed(1)}/{area.weight}
                  </strong>
                </div>
                <p>{area.rationale}</p>
                <ul>
                  {area.evidence.map((item) => <li key={item}>{item}</li>)}
                </ul>
              </section>
            ))}
            <h4>실행 가능한 개선안</h4>
            <ul>
              {(result.schoolImprovements[schoolResult.school.schoolCode] ?? [])
                .map((item) => <li key={item}>{item}</li>)}
            </ul>
          </article>
        ))}
      </div>
      {result.qualityWarnings.length > 0 && (
        <div className="quality-warning">
          <strong>품질 검토 참고사항</strong>
          <ul>
            {result.qualityWarnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </div>
      )}
      <p className="disclaimer">{result.disclaimer}</p>
    </section>
  );
}

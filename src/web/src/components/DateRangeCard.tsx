import { useEffect, useRef, useState } from "react";
import { DayPicker, type DateRange } from "react-day-picker";
import { ko } from "react-day-picker/locale";
import {
  formatKoreanRange,
  getDatePolicy,
} from "../utils/dates";

type DateRangeCardProps = {
  disabled: boolean;
  range: DateRange | undefined;
  onChange: (range: DateRange | undefined) => void;
};

export function DateRangeCard({
  disabled,
  range,
  onChange,
}: DateRangeCardProps) {
  const [open, setOpen] = useState(false);
  const popoverRef = useRef<HTMLDivElement>(null);
  const policy = getDatePolicy();

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
    <section className={`card date-card ${disabled ? "is-disabled" : ""}`}>
      <div className="step-label">02 · 날짜 선택</div>
      <h2>언제 먹은 급식인가요?</h2>
      <p className="supporting">
        현재 달과 바로 이전 달의 중식을 조회할 수 있어요.
      </p>
      <div className="date-control" ref={popoverRef}>
        <button
          className="date-trigger"
          type="button"
          disabled={disabled}
          aria-expanded={open}
          aria-haspopup="dialog"
          onClick={() => setOpen((value) => !value)}
        >
          <span aria-hidden="true">▦</span>
          <span>{formatKoreanRange(range)}</span>
        </button>
        {open && (
          <div className="calendar-popover" role="dialog" aria-label="날짜 범위 선택">
            <DayPicker
              mode="range"
              locale={ko}
              selected={range}
              onSelect={onChange}
              defaultMonth={range?.to ?? policy.today}
              startMonth={policy.min}
              endMonth={policy.max}
              disabled={{ before: policy.min, after: policy.max }}
              showOutsideDays
              required={false}
            />
            <button className="text-button" type="button" onClick={() => onChange(undefined)}>
              선택 초기화
            </button>
          </div>
        )}
      </div>
      <p className="date-summary" aria-live="polite">
        {formatKoreanRange(range)}
      </p>
      {!range?.from || !range.to ? (
        <p className="field-message">시작일과 종료일을 모두 선택해 주세요.</p>
      ) : null}
    </section>
  );
}

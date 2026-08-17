import {
  endOfMonth,
  format,
  parseISO,
  startOfMonth,
  subDays,
  subMonths,
} from "date-fns";
import { ko } from "date-fns/locale";
import type { DateRange } from "react-day-picker";

function todayInSeoul(): Date {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Seoul",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts();
  const value = Object.fromEntries(parts.map(({ type, value }) => [type, value]));
  return parseISO(`${value.year}-${value.month}-${value.day}`);
}

export function getDatePolicy(now = todayInSeoul()) {
  return {
    today: now,
    min: startOfMonth(subMonths(now, 1)),
    max: endOfMonth(now),
    initial: { from: subDays(now, 6), to: now } satisfies DateRange,
  };
}

export function toApiDate(date: Date): string {
  return format(date, "yyyy-MM-dd");
}

export function formatKoreanDate(date: Date): string {
  return format(date, "yyyy년 M월 d일 (EEE)", { locale: ko });
}

export function formatKoreanRange(range: DateRange | undefined): string {
  if (!range?.from) return "날짜 범위를 선택해 주세요.";
  if (!range.to) return `${formatKoreanDate(range.from)}부터 종료일 선택`;
  return `${formatKoreanDate(range.from)} ~ ${formatKoreanDate(range.to)}`;
}

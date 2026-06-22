const CHINA_TIME_ZONE = "Asia/Shanghai";

type ChinaDatePart = "year" | "month" | "day" | "hour" | "minute" | "second";

function chinaParts(date: Date = new Date()): Record<ChinaDatePart, string> {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: CHINA_TIME_ZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hourCycle: "h23",
  }).formatToParts(date);

  const values = Object.fromEntries(
    parts
      .filter((part) => part.type !== "literal")
      .map((part) => [part.type, part.value])
  );

  return {
    year: values.year ?? "1970",
    month: values.month ?? "01",
    day: values.day ?? "01",
    hour: values.hour ?? "00",
    minute: values.minute ?? "00",
    second: values.second ?? "00",
  };
}

export function chinaDate(date: Date = new Date()): string {
  const parts = chinaParts(date);
  return `${parts.year}-${parts.month}-${parts.day}`;
}

export function chinaTime(date: Date = new Date(), includeSeconds = true): string {
  const parts = chinaParts(date);
  return includeSeconds
    ? `${parts.hour}:${parts.minute}:${parts.second}`
    : `${parts.hour}:${parts.minute}`;
}

export function chinaDateTime(date: Date = new Date(), includeSeconds = true): string {
  return `${chinaDate(date)} ${chinaTime(date, includeSeconds)}`;
}

export function chinaHourMinute(date: Date = new Date()): { hour: number; minute: number } {
  const parts = chinaParts(date);
  return {
    hour: Number(parts.hour),
    minute: Number(parts.minute),
  };
}

export function chinaWeekday(date: Date = new Date()): number {
  const weekday = new Intl.DateTimeFormat("en-US", {
    timeZone: CHINA_TIME_ZONE,
    weekday: "short",
  }).format(date);

  const map: Record<string, number> = {
    Sun: 0,
    Mon: 1,
    Tue: 2,
    Wed: 3,
    Thu: 4,
    Fri: 5,
    Sat: 6,
  };

  return map[weekday] ?? 0;
}


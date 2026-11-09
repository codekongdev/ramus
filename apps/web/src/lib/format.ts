import type { Locale } from './locale';

/**
 * Date, time and number display (roadmap 9.3 규칙 4). Screens never assemble date strings
 * themselves; they call these with the current locale. Server times are ISO 8601 UTC
 * (contracts.md 1장) and are shown in the viewer's time zone unless `timeZone` is given.
 */

export interface FormatOptions {
  /** IANA zone. Defaults to the runtime's zone; tests pin it. */
  readonly timeZone?: string;
}

const toDate = (value: string | Date): Date => {
  const date = typeof value === 'string' ? new Date(value) : value;
  if (Number.isNaN(date.getTime())) throw new RangeError(`Invalid date: ${String(value)}`);
  return date;
};

/** e.g. ko: "2026. 11. 9." · en: "Nov 9, 2026" */
export function formatDate(value: string | Date, locale: Locale, options: FormatOptions = {}): string {
  return new Intl.DateTimeFormat(locale, { dateStyle: 'medium', timeZone: options.timeZone }).format(
    toDate(value),
  );
}

/** e.g. ko: "2026. 11. 9. 오후 1:17" · en: "Nov 9, 2026, 1:17 PM" */
export function formatDateTime(value: string | Date, locale: Locale, options: FormatOptions = {}): string {
  return new Intl.DateTimeFormat(locale, {
    dateStyle: 'medium',
    timeStyle: 'short',
    timeZone: options.timeZone,
  }).format(toDate(value));
}

/** e.g. ko: "오후 1:17" · en: "1:17 PM" */
export function formatTime(value: string | Date, locale: Locale, options: FormatOptions = {}): string {
  return new Intl.DateTimeFormat(locale, { timeStyle: 'short', timeZone: options.timeZone }).format(
    toDate(value),
  );
}

const RELATIVE_UNITS: readonly [Intl.RelativeTimeFormatUnit, number][] = [
  ['year', 365 * 24 * 60 * 60],
  ['month', 30 * 24 * 60 * 60],
  ['week', 7 * 24 * 60 * 60],
  ['day', 24 * 60 * 60],
  ['hour', 60 * 60],
  ['minute', 60],
];

/**
 * e.g. ko: "3분 전", "어제", "방금" · en: "3 minutes ago", "yesterday", "now".
 * `now` is a parameter so callers (and tests) control the clock.
 */
export function formatRelativeTime(value: string | Date, now: Date, locale: Locale): string {
  const seconds = Math.round((toDate(value).getTime() - now.getTime()) / 1000);
  const rtf = new Intl.RelativeTimeFormat(locale, { numeric: 'auto' });
  for (const [unit, size] of RELATIVE_UNITS) {
    if (Math.abs(seconds) >= size) return rtf.format(Math.trunc(seconds / size), unit);
  }
  return rtf.format(0, 'second');
}

/** e.g. ko/en: "20,000" */
export function formatNumber(value: number, locale: Locale): string {
  return new Intl.NumberFormat(locale).format(value);
}

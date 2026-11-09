import { describe, expect, it } from 'vitest';
import {
  formatDate,
  formatDateTime,
  formatNumber,
  formatRelativeTime,
  formatTime,
} from '../../src/lib/format';

const iso = '2026-11-09T04:17:23Z'; // 13:17 in Asia/Seoul
const seoul = { timeZone: 'Asia/Seoul' };

// The day-period label differs across ICU versions (e.g. "오후 1:17" vs "PM 1:17" in
// Node 24.13 / ICU 78.2), so only the label is matched loosely; digits stay exact.
const koAfternoon = String.raw`(?:오후|PM)\s1:17`;

describe('date formatting', () => {
  it('formats in the given locale and zone', () => {
    expect(formatDate(iso, 'ko', seoul)).toBe('2026. 11. 9.');
    expect(formatDate(iso, 'en', seoul)).toBe('Nov 9, 2026');
    expect(formatTime(iso, 'ko', seoul)).toMatch(new RegExp(`^${koAfternoon}$`));
    expect(formatTime(iso, 'en', seoul)).toMatch(/^1:17\sPM$/);
    expect(formatDateTime(iso, 'ko', seoul)).toMatch(new RegExp(`^2026\\. 11\\. 9\\.,?\\s${koAfternoon}$`));
  });

  it('uses the zone to pick the calendar day', () => {
    expect(formatDate('2026-11-09T20:00:00Z', 'ko', seoul)).toBe('2026. 11. 10.');
    expect(formatDate('2026-11-09T20:00:00Z', 'ko', { timeZone: 'UTC' })).toBe('2026. 11. 9.');
  });

  it('rejects invalid dates instead of printing "Invalid Date"', () => {
    expect(() => formatDate('not a date', 'ko')).toThrow(RangeError);
  });
});

describe('formatRelativeTime', () => {
  const now = new Date(iso);
  const ago = (seconds: number) => new Date(now.getTime() - seconds * 1000);

  it.each([
    [10, '지금', 'now'],
    [3 * 60, '3분 전', '3 minutes ago'],
    [2 * 60 * 60, '2시간 전', '2 hours ago'],
    [24 * 60 * 60, '어제', 'yesterday'],
    [8 * 24 * 60 * 60, '지난주', 'last week'],
  ])('%is ago', (seconds, ko, en) => {
    expect(formatRelativeTime(ago(seconds), now, 'ko')).toBe(ko);
    expect(formatRelativeTime(ago(seconds), now, 'en')).toBe(en);
  });

  it('handles future times', () => {
    expect(formatRelativeTime(new Date(now.getTime() + 5 * 60 * 1000), now, 'ko')).toBe('5분 후');
  });
});

describe('formatNumber', () => {
  it('groups digits', () => {
    expect(formatNumber(20000, 'ko')).toBe('20,000');
    expect(formatNumber(100000, 'en')).toBe('100,000');
  });
});

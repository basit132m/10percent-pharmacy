/**
 * Offer status logic — the single source of truth for this server.
 *
 * NOTE: functions/src/status.ts is a twin of this file, kept for the Cloud
 * Functions deployment path (which needs the Firebase Blaze plan). This VPS
 * server is the live implementation. If you change a rule here, change it
 * there too, or delete functions/ if you never intend to go back.
 *
 * Dates are plain 'YYYY-MM-DD' strings in the pharmacy's timezone: an offer
 * expires on a day, and a calendar date has no timezone edge cases.
 */

export const TIME_ZONE = 'Asia/Karachi';

/** An offer flips to EXPIRING SOON this many days before its expiry date. */
export const EXPIRING_SOON_WINDOW_DAYS = 3;

export const OFFER_STATUSES = ['active', 'expiring_soon', 'expired'] as const;

export type OfferStatus = (typeof OFFER_STATUSES)[number];

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

export function isIsoDate(value: unknown): value is string {
  if (typeof value !== 'string' || !ISO_DATE.test(value)) {
    return false;
  }
  const [year, month, day] = value.split('-').map(Number);
  const parsed = new Date(Date.UTC(year, month - 1, day));
  return (
    parsed.getUTCFullYear() === year &&
    parsed.getUTCMonth() === month - 1 &&
    parsed.getUTCDate() === day
  );
}

/** Today's calendar date in the pharmacy timezone, as 'YYYY-MM-DD'. */
export function pharmacyToday(now: Date = new Date()): string {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: TIME_ZONE,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(now);
}

function toUtcMillis(isoDate: string): number {
  const [year, month, day] = isoDate.split('-').map(Number);
  return Date.UTC(year, month - 1, day);
}

/** Whole days from `fromDate` to `toDate` (negative when `toDate` is earlier). */
export function daysBetween(fromDate: string, toDate: string): number {
  const dayMs = 24 * 60 * 60 * 1000;
  return Math.round((toUtcMillis(toDate) - toUtcMillis(fromDate)) / dayMs);
}

/**
 * The status an offer should have on `today`:
 *   today  >  expiry                       -> expired
 *   expiry - 3 days <= today <= expiry     -> expiring_soon
 *   otherwise                              -> active
 */
export function computeOfferStatus(
  expiryDate: string,
  today: string = pharmacyToday(),
): OfferStatus {
  const daysLeft = daysBetween(today, expiryDate);
  if (daysLeft < 0) {
    return 'expired';
  }
  if (daysLeft <= EXPIRING_SOON_WINDOW_DAYS) {
    return 'expiring_soon';
  }
  return 'active';
}

/**
 * Milliseconds until the next daily run, which happens just after midnight in
 * the pharmacy timezone so statuses flip on the correct day.
 */
export function millisUntilNextDailyRun(now: Date = new Date()): number {
  const target = { hour: 0, minute: 5 };
  const parts = new Intl.DateTimeFormat('en-GB', {
    timeZone: TIME_ZONE,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).formatToParts(now);

  const read = (type: string) =>
    Number(parts.find((part) => part.type === type)?.value ?? '0');

  const minutesNow = read('hour') * 60 + read('minute');
  const minutesTarget = target.hour * 60 + target.minute;
  let deltaMinutes = minutesTarget - minutesNow;
  if (deltaMinutes <= 0) {
    deltaMinutes += 24 * 60;
  }
  // Subtract the seconds already elapsed in the current minute.
  return deltaMinutes * 60_000 - read('second') * 1000;
}

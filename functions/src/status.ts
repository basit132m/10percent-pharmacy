/**
 * Offer status logic.
 *
 * Everything here is pure so it can be unit tested without Firebase, and it is
 * the single source of truth for statuses: the scheduled job stamps the result
 * onto every offer document so the dashboard and the Android app just read a
 * field instead of each computing their own idea of "expiring soon".
 *
 * Dates are plain 'YYYY-MM-DD' strings interpreted in the pharmacy's local
 * timezone. A bonus offer expires "on a day", not at an instant, so a calendar
 * date avoids every timezone edge case a Timestamp would introduce.
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
  // 'en-CA' formats as YYYY-MM-DD, which is exactly the shape we store.
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
 *
 * An offer whose start date is still in the future is ACTIVE: the admin
 * publishes it so stores can plan ahead, and the spec has no "scheduled" state.
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

export function isOfferStatus(value: unknown): value is OfferStatus {
  return OFFER_STATUSES.includes(value as OfferStatus);
}

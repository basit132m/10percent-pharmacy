"use strict";
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
Object.defineProperty(exports, "__esModule", { value: true });
exports.OFFER_STATUSES = exports.EXPIRING_SOON_WINDOW_DAYS = exports.TIME_ZONE = void 0;
exports.isIsoDate = isIsoDate;
exports.pharmacyToday = pharmacyToday;
exports.daysBetween = daysBetween;
exports.computeOfferStatus = computeOfferStatus;
exports.isOfferStatus = isOfferStatus;
exports.TIME_ZONE = 'Asia/Karachi';
/** An offer flips to EXPIRING SOON this many days before its expiry date. */
exports.EXPIRING_SOON_WINDOW_DAYS = 3;
exports.OFFER_STATUSES = ['active', 'expiring_soon', 'expired'];
const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;
function isIsoDate(value) {
    if (typeof value !== 'string' || !ISO_DATE.test(value)) {
        return false;
    }
    const [year, month, day] = value.split('-').map(Number);
    const parsed = new Date(Date.UTC(year, month - 1, day));
    return (parsed.getUTCFullYear() === year &&
        parsed.getUTCMonth() === month - 1 &&
        parsed.getUTCDate() === day);
}
/** Today's calendar date in the pharmacy timezone, as 'YYYY-MM-DD'. */
function pharmacyToday(now = new Date()) {
    // 'en-CA' formats as YYYY-MM-DD, which is exactly the shape we store.
    return new Intl.DateTimeFormat('en-CA', {
        timeZone: exports.TIME_ZONE,
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
    }).format(now);
}
function toUtcMillis(isoDate) {
    const [year, month, day] = isoDate.split('-').map(Number);
    return Date.UTC(year, month - 1, day);
}
/** Whole days from `fromDate` to `toDate` (negative when `toDate` is earlier). */
function daysBetween(fromDate, toDate) {
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
function computeOfferStatus(expiryDate, today = pharmacyToday()) {
    const daysLeft = daysBetween(today, expiryDate);
    if (daysLeft < 0) {
        return 'expired';
    }
    if (daysLeft <= exports.EXPIRING_SOON_WINDOW_DAYS) {
        return 'expiring_soon';
    }
    return 'active';
}
function isOfferStatus(value) {
    return exports.OFFER_STATUSES.includes(value);
}
//# sourceMappingURL=status.js.map
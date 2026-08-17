/**
 * Shared offer vocabulary for the dashboard.
 *
 * The status written here is only a first guess so the new card looks right
 * immediately — the Cloud Functions own the real status and will correct it.
 * Keep the rules in sync with functions/src/status.ts.
 */
import type { Timestamp } from 'firebase/firestore';

export const TIME_ZONE = 'Asia/Karachi';
export const EXPIRING_SOON_WINDOW_DAYS = 3;

export type OfferStatus = 'active' | 'expiring_soon' | 'expired';

export interface Offer {
  id: string;
  productName: string;
  buyQty: number;
  freeQty: number;
  startDate: string;
  expiryDate: string;
  status: OfferStatus;
  createdBy: string;
  createdAt: Timestamp | null;
  notifiedCount?: number;
}

export interface StoreOwner {
  id: string;
  username: string;
  storeName: string | null;
  ownerName: string | null;
  phone: string | null;
  address: string | null;
  isActive: boolean;
  createdAt: Timestamp | null;
}

export interface NotificationLogEntry {
  id: string;
  offerId: string;
  productName: string;
  title: string;
  body: string;
  recipientCount: number;
  successCount: number;
  failureCount: number;
  sentAt: Timestamp | null;
}

export const STATUS_LABELS: Record<OfferStatus, string> = {
  active: 'Active',
  expiring_soon: 'Expiring Soon',
  expired: 'Expired',
};

/** Today's date in the pharmacy timezone as 'YYYY-MM-DD'. */
export function pharmacyToday(now: Date = new Date()): string {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: TIME_ZONE,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(now);
}

export function daysBetween(fromDate: string, toDate: string): number {
  const toMillis = (iso: string) => {
    const [y, m, d] = iso.split('-').map(Number);
    return Date.UTC(y, m - 1, d);
  };
  return Math.round((toMillis(toDate) - toMillis(fromDate)) / 86_400_000);
}

export function computeOfferStatus(
  expiryDate: string,
  today: string = pharmacyToday(),
): OfferStatus {
  const daysLeft = daysBetween(today, expiryDate);
  if (daysLeft < 0) return 'expired';
  if (daysLeft <= EXPIRING_SOON_WINDOW_DAYS) return 'expiring_soon';
  return 'active';
}

export function offerHeadline(offer: Pick<Offer, 'buyQty' | 'freeQty'>): string {
  return `Buy ${offer.buyQty} Get ${offer.freeQty} Free`;
}

/** '2026-08-17' -> '17 Aug 2026'. */
export function formatDate(isoDate: string): string {
  const [y, m, d] = isoDate.split('-').map(Number);
  return new Intl.DateTimeFormat('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    timeZone: 'UTC',
  }).format(new Date(Date.UTC(y, m - 1, d)));
}

export function formatTimestamp(value: Timestamp | null): string {
  if (!value) return '—';
  return new Intl.DateTimeFormat('en-GB', {
    dateStyle: 'medium',
    timeStyle: 'short',
    timeZone: TIME_ZONE,
  }).format(value.toDate());
}

export function expiryHint(offer: Offer, today = pharmacyToday()): string {
  const daysLeft = daysBetween(today, offer.expiryDate);
  if (daysLeft < 0) return `Expired ${Math.abs(daysLeft)} day(s) ago`;
  if (daysLeft === 0) return 'Expires today';
  if (daysLeft === 1) return 'Expires tomorrow';
  return `${daysLeft} days left`;
}

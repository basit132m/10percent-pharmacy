/**
 * Offer status maintenance.
 *
 * Statuses are stamped onto the documents server-side so every client sees the
 * same badge regardless of when it last opened the app or what its device clock
 * says. A daily job does the flipping; an update trigger keeps an edited offer
 * consistent straight away instead of waiting for the next run.
 */
import { FieldValue } from 'firebase-admin/firestore';
import { logger } from 'firebase-functions';
import { onDocumentUpdated } from 'firebase-functions/v2/firestore';
import { onCall } from 'firebase-functions/v2/https';
import { onSchedule } from 'firebase-functions/v2/scheduler';

import { db, OFFERS } from './firebase';
import { requireAdmin } from './guards';
import { computeOfferStatus, isIsoDate, pharmacyToday, TIME_ZONE } from './status';

/** Firestore allows 500 writes per batch; leave headroom. */
const BATCH_LIMIT = 400;

export interface RefreshResult {
  today: string;
  scanned: number;
  updated: number;
}

export async function refreshOfferStatuses(
  today: string = pharmacyToday(),
): Promise<RefreshResult> {
  const snapshot = await db.collection(OFFERS).get();
  let updated = 0;
  let batch = db.batch();
  let pending = 0;

  for (const doc of snapshot.docs) {
    const expiryDate: unknown = doc.get('expiryDate');
    if (!isIsoDate(expiryDate)) {
      logger.warn('Offer has an unusable expiry date, skipping', { offerId: doc.id });
      continue;
    }
    const status = computeOfferStatus(expiryDate, today);
    if (status === doc.get('status')) {
      continue;
    }
    batch.update(doc.ref, { status, updatedAt: FieldValue.serverTimestamp() });
    updated += 1;
    pending += 1;
    if (pending === BATCH_LIMIT) {
      await batch.commit();
      batch = db.batch();
      pending = 0;
    }
  }

  if (pending > 0) {
    await batch.commit();
  }

  logger.info('Offer statuses refreshed', {
    today,
    scanned: snapshot.size,
    updated,
  });
  return { today, scanned: snapshot.size, updated };
}

/** Runs just after midnight in Karachi, so statuses flip on the right day. */
export const dailyOfferStatusCheck = onSchedule(
  { schedule: '5 0 * * *', timeZone: TIME_ZONE },
  async () => {
    await refreshOfferStatuses();
  },
);

/** Lets the admin force a re-check from the dashboard (also handy in testing). */
export const refreshOfferStatusesNow = onCall(async (request) => {
  requireAdmin(request);
  return refreshOfferStatuses();
});

/**
 * Keep an edited offer's status honest. Writes only when the stored status is
 * actually wrong, so this cannot loop on its own update.
 */
export const syncOfferStatusOnEdit = onDocumentUpdated(
  `${OFFERS}/{offerId}`,
  async (event) => {
    const after = event.data?.after;
    if (!after) {
      return;
    }
    const expiryDate: unknown = after.get('expiryDate');
    if (!isIsoDate(expiryDate)) {
      return;
    }
    const expected = computeOfferStatus(expiryDate);
    if (expected === after.get('status')) {
      return;
    }
    await after.ref.update({ status: expected });
    logger.info('Offer status corrected after edit', {
      offerId: event.params.offerId,
      status: expected,
    });
  },
);

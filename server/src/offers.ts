/**
 * Offer status maintenance.
 *
 * Statuses are stamped onto the documents by this server so every client sees
 * the same badge regardless of when it last opened the app or what its device
 * clock says. A daily pass does the flipping; a listener keeps an edited offer
 * consistent straight away instead of waiting for the next run.
 */
import { FieldValue } from 'firebase-admin/firestore';
import { Router } from 'express';

import { db, OFFERS } from './firebase';
import { requireAdmin } from './auth';
import {
  computeOfferStatus,
  isIsoDate,
  millisUntilNextDailyRun,
  pharmacyToday,
} from './status';

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
  const snapshot = await db().collection(OFFERS).get();
  let updated = 0;
  let batch = db().batch();
  let pending = 0;

  for (const doc of snapshot.docs) {
    const expiryDate: unknown = doc.get('expiryDate');
    if (!isIsoDate(expiryDate)) {
      console.warn(`[offers] ${doc.id} has an unusable expiry date, skipping`);
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
      batch = db().batch();
      pending = 0;
    }
  }

  if (pending > 0) {
    await batch.commit();
  }

  console.log(
    `[offers] status pass for ${today}: ${updated} of ${snapshot.size} updated`,
  );
  return { today, scanned: snapshot.size, updated };
}

/**
 * Runs the status pass just after midnight in the pharmacy timezone, then
 * re-arms itself. Re-computing the delay each time keeps it correct across
 * daylight-saving shifts and long uptimes, which a fixed 24h interval would
 * slowly drift away from.
 */
export function scheduleDailyStatusPass(): () => void {
  let timer: NodeJS.Timeout;

  const arm = () => {
    const delay = millisUntilNextDailyRun();
    console.log(
      `[offers] next status pass in ${Math.round(delay / 60_000)} minutes`,
    );
    timer = setTimeout(async () => {
      try {
        await refreshOfferStatuses();
      } catch (error) {
        console.error('[offers] daily status pass failed:', error);
      }
      arm();
    }, delay);
  };

  arm();
  return () => clearTimeout(timer);
}

/**
 * Keeps an edited offer's status honest. Writes only when the stored status is
 * actually wrong, so this cannot loop on its own update.
 */
export function watchOfferEdits(): () => void {
  return db()
    .collection(OFFERS)
    .onSnapshot(
      (snapshot) => {
        for (const change of snapshot.docChanges()) {
          if (change.type === 'removed') {
            continue;
          }
          const doc = change.doc;
          const expiryDate: unknown = doc.get('expiryDate');
          if (!isIsoDate(expiryDate)) {
            continue;
          }
          const expected = computeOfferStatus(expiryDate);
          if (expected === doc.get('status')) {
            continue;
          }
          doc.ref
            .update({ status: expected })
            .then(() => console.log(`[offers] ${doc.id} status -> ${expected}`))
            .catch((error) =>
              console.warn(`[offers] could not correct ${doc.id}:`, error),
            );
        }
      },
      (error) => console.error('[offers] edit listener error:', error),
    );
}

export const offersRouter = Router();

/** Lets the admin force a re-check from the dashboard. */
offersRouter.post('/refresh-status', requireAdmin, async (_req, res, next) => {
  try {
    res.json(await refreshOfferStatuses());
  } catch (error) {
    next(error);
  }
});

"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.syncOfferStatusOnEdit = exports.refreshOfferStatusesNow = exports.dailyOfferStatusCheck = void 0;
exports.refreshOfferStatuses = refreshOfferStatuses;
/**
 * Offer status maintenance.
 *
 * Statuses are stamped onto the documents server-side so every client sees the
 * same badge regardless of when it last opened the app or what its device clock
 * says. A daily job does the flipping; an update trigger keeps an edited offer
 * consistent straight away instead of waiting for the next run.
 */
const firestore_1 = require("firebase-admin/firestore");
const firebase_functions_1 = require("firebase-functions");
const firestore_2 = require("firebase-functions/v2/firestore");
const https_1 = require("firebase-functions/v2/https");
const scheduler_1 = require("firebase-functions/v2/scheduler");
const firebase_1 = require("./firebase");
const guards_1 = require("./guards");
const status_1 = require("./status");
/** Firestore allows 500 writes per batch; leave headroom. */
const BATCH_LIMIT = 400;
async function refreshOfferStatuses(today = (0, status_1.pharmacyToday)()) {
    const snapshot = await firebase_1.db.collection(firebase_1.OFFERS).get();
    let updated = 0;
    let batch = firebase_1.db.batch();
    let pending = 0;
    for (const doc of snapshot.docs) {
        const expiryDate = doc.get('expiryDate');
        if (!(0, status_1.isIsoDate)(expiryDate)) {
            firebase_functions_1.logger.warn('Offer has an unusable expiry date, skipping', { offerId: doc.id });
            continue;
        }
        const status = (0, status_1.computeOfferStatus)(expiryDate, today);
        if (status === doc.get('status')) {
            continue;
        }
        batch.update(doc.ref, { status, updatedAt: firestore_1.FieldValue.serverTimestamp() });
        updated += 1;
        pending += 1;
        if (pending === BATCH_LIMIT) {
            await batch.commit();
            batch = firebase_1.db.batch();
            pending = 0;
        }
    }
    if (pending > 0) {
        await batch.commit();
    }
    firebase_functions_1.logger.info('Offer statuses refreshed', {
        today,
        scanned: snapshot.size,
        updated,
    });
    return { today, scanned: snapshot.size, updated };
}
/** Runs just after midnight in Karachi, so statuses flip on the right day. */
exports.dailyOfferStatusCheck = (0, scheduler_1.onSchedule)({ schedule: '5 0 * * *', timeZone: status_1.TIME_ZONE }, async () => {
    await refreshOfferStatuses();
});
/** Lets the admin force a re-check from the dashboard (also handy in testing). */
exports.refreshOfferStatusesNow = (0, https_1.onCall)(async (request) => {
    (0, guards_1.requireAdmin)(request);
    return refreshOfferStatuses();
});
/**
 * Keep an edited offer's status honest. Writes only when the stored status is
 * actually wrong, so this cannot loop on its own update.
 */
exports.syncOfferStatusOnEdit = (0, firestore_2.onDocumentUpdated)(`${firebase_1.OFFERS}/{offerId}`, async (event) => {
    const after = event.data?.after;
    if (!after) {
        return;
    }
    const expiryDate = after.get('expiryDate');
    if (!(0, status_1.isIsoDate)(expiryDate)) {
        return;
    }
    const expected = (0, status_1.computeOfferStatus)(expiryDate);
    if (expected === after.get('status')) {
        return;
    }
    await after.ref.update({ status: expected });
    firebase_functions_1.logger.info('Offer status corrected after edit', {
        offerId: event.params.offerId,
        status: expected,
    });
});
//# sourceMappingURL=offers.js.map
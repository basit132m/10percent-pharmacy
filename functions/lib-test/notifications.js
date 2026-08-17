"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.onOfferPublished = void 0;
exports.offerHeadline = offerHeadline;
exports.notifyStoresAboutOffer = notifyStoresAboutOffer;
/**
 * Push notifications.
 *
 * When the admin publishes an offer, every active store owner gets a push.
 * Tokens live on the store's user document (the app writes its own token there
 * on login and drops it on logout); tokens FCM tells us are dead are pruned.
 */
const firestore_1 = require("firebase-admin/firestore");
const firebase_functions_1 = require("firebase-functions");
const firestore_2 = require("firebase-functions/v2/firestore");
const firebase_1 = require("./firebase");
/** FCM rejects multicasts larger than this. */
const MULTICAST_BATCH_SIZE = 500;
const DEAD_TOKEN_CODES = new Set([
    'messaging/registration-token-not-registered',
    'messaging/invalid-registration-token',
    'messaging/invalid-argument',
]);
function offerHeadline(offer) {
    return `Buy ${offer.buyQty} Get ${offer.freeQty} Free`;
}
async function activeStoreTokens() {
    const snapshot = await firebase_1.db
        .collection(firebase_1.USERS)
        .where('role', '==', 'store_owner')
        .where('isActive', '==', true)
        .get();
    const owners = [];
    const seen = new Set();
    for (const doc of snapshot.docs) {
        const tokens = doc.get('fcmTokens');
        if (!Array.isArray(tokens)) {
            continue;
        }
        for (const token of tokens) {
            if (typeof token === 'string' && token.length > 0 && !seen.has(token)) {
                seen.add(token);
                owners.push({ uid: doc.id, token });
            }
        }
    }
    return owners;
}
async function pruneTokens(deadTokensByUid) {
    const removals = [...deadTokensByUid].map(([uid, tokens]) => firebase_1.db
        .collection(firebase_1.USERS)
        .doc(uid)
        .update({ fcmTokens: firestore_1.FieldValue.arrayRemove(...tokens) })
        .catch((error) => firebase_functions_1.logger.warn('Could not prune FCM tokens', { uid, error })));
    await Promise.all(removals);
}
async function notifyStoresAboutOffer(offerId, offer) {
    const recipients = await activeStoreTokens();
    const title = `New bonus offer: ${offer.productName}`;
    const body = `${offerHeadline(offer)} — valid until ${offer.expiryDate}`;
    if (recipients.length === 0) {
        firebase_functions_1.logger.info('No active store owners with push tokens', { offerId });
        await firebase_1.db.collection(firebase_1.NOTIFICATIONS_LOG).add({
            offerId,
            productName: offer.productName,
            title,
            body,
            recipientCount: 0,
            successCount: 0,
            failureCount: 0,
            sentAt: firestore_1.FieldValue.serverTimestamp(),
        });
        return { recipientCount: 0, successCount: 0, failureCount: 0 };
    }
    let successCount = 0;
    let failureCount = 0;
    const deadTokensByUid = new Map();
    for (let i = 0; i < recipients.length; i += MULTICAST_BATCH_SIZE) {
        const batch = recipients.slice(i, i + MULTICAST_BATCH_SIZE);
        const message = {
            tokens: batch.map((recipient) => recipient.token),
            notification: { title, body },
            // The app reads these to open the right offer when the push is tapped.
            data: {
                type: 'new_offer',
                offerId,
                productName: offer.productName,
                expiryDate: offer.expiryDate,
            },
            android: {
                priority: 'high',
                notification: {
                    channelId: 'bonus_offers',
                    clickAction: 'OPEN_OFFER_DETAIL',
                },
            },
        };
        const response = await firebase_1.messaging.sendEachForMulticast(message);
        successCount += response.successCount;
        failureCount += response.failureCount;
        response.responses.forEach((result, index) => {
            if (result.success) {
                return;
            }
            const code = result.error?.code ?? '';
            const { uid, token } = batch[index];
            if (DEAD_TOKEN_CODES.has(code)) {
                deadTokensByUid.set(uid, [...(deadTokensByUid.get(uid) ?? []), token]);
            }
            else {
                firebase_functions_1.logger.warn('Push delivery failed', { uid, code });
            }
        });
    }
    if (deadTokensByUid.size > 0) {
        await pruneTokens(deadTokensByUid);
    }
    await firebase_1.db.collection(firebase_1.NOTIFICATIONS_LOG).add({
        offerId,
        productName: offer.productName,
        title,
        body,
        recipientCount: recipients.length,
        successCount,
        failureCount,
        sentAt: firestore_1.FieldValue.serverTimestamp(),
    });
    firebase_functions_1.logger.info('Offer notification sent', {
        offerId,
        recipientCount: recipients.length,
        successCount,
        failureCount,
    });
    return { recipientCount: recipients.length, successCount, failureCount };
}
/** Publishing an offer = creating the document. */
exports.onOfferPublished = (0, firestore_2.onDocumentCreated)(`${firebase_1.OFFERS}/{offerId}`, async (event) => {
    const snapshot = event.data;
    if (!snapshot) {
        return;
    }
    const offer = snapshot.data();
    const offerId = event.params.offerId;
    const result = await notifyStoresAboutOffer(offerId, offer);
    await snapshot.ref.update({
        notifiedAt: firestore_1.FieldValue.serverTimestamp(),
        notifiedCount: result.recipientCount,
    });
});
//# sourceMappingURL=notifications.js.map
/**
 * Push notifications.
 *
 * When the admin publishes an offer, every active store owner gets a push.
 * Tokens live on the store's user document (the app writes its own token there
 * on login and drops it on logout); tokens FCM tells us are dead are pruned.
 */
import { FieldValue } from 'firebase-admin/firestore';
import type { MulticastMessage } from 'firebase-admin/messaging';
import { logger } from 'firebase-functions';
import { onDocumentCreated } from 'firebase-functions/v2/firestore';

import { db, messaging, NOTIFICATIONS_LOG, OFFERS, USERS } from './firebase';
import type { OfferDoc } from './types';

/** FCM rejects multicasts larger than this. */
const MULTICAST_BATCH_SIZE = 500;

const DEAD_TOKEN_CODES = new Set([
  'messaging/registration-token-not-registered',
  'messaging/invalid-registration-token',
  'messaging/invalid-argument',
]);

export function offerHeadline(offer: Pick<OfferDoc, 'buyQty' | 'freeQty'>): string {
  return `Buy ${offer.buyQty} Get ${offer.freeQty} Free`;
}

interface TokenOwner {
  uid: string;
  token: string;
}

async function activeStoreTokens(): Promise<TokenOwner[]> {
  const snapshot = await db
    .collection(USERS)
    .where('role', '==', 'store_owner')
    .where('isActive', '==', true)
    .get();

  const owners: TokenOwner[] = [];
  const seen = new Set<string>();
  for (const doc of snapshot.docs) {
    const tokens: unknown = doc.get('fcmTokens');
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

async function pruneTokens(deadTokensByUid: Map<string, string[]>): Promise<void> {
  const removals = [...deadTokensByUid].map(([uid, tokens]) =>
    db
      .collection(USERS)
      .doc(uid)
      .update({ fcmTokens: FieldValue.arrayRemove(...tokens) })
      .catch((error) => logger.warn('Could not prune FCM tokens', { uid, error })),
  );
  await Promise.all(removals);
}

export async function notifyStoresAboutOffer(
  offerId: string,
  offer: OfferDoc,
): Promise<{ recipientCount: number; successCount: number; failureCount: number }> {
  const recipients = await activeStoreTokens();
  const title = `New bonus offer: ${offer.productName}`;
  const body = `${offerHeadline(offer)} — valid until ${offer.expiryDate}`;

  if (recipients.length === 0) {
    logger.info('No active store owners with push tokens', { offerId });
    await db.collection(NOTIFICATIONS_LOG).add({
      offerId,
      productName: offer.productName,
      title,
      body,
      recipientCount: 0,
      successCount: 0,
      failureCount: 0,
      sentAt: FieldValue.serverTimestamp(),
    });
    return { recipientCount: 0, successCount: 0, failureCount: 0 };
  }

  let successCount = 0;
  let failureCount = 0;
  const deadTokensByUid = new Map<string, string[]>();

  for (let i = 0; i < recipients.length; i += MULTICAST_BATCH_SIZE) {
    const batch = recipients.slice(i, i + MULTICAST_BATCH_SIZE);
    const message: MulticastMessage = {
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

    const response = await messaging.sendEachForMulticast(message);
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
      } else {
        logger.warn('Push delivery failed', { uid, code });
      }
    });
  }

  if (deadTokensByUid.size > 0) {
    await pruneTokens(deadTokensByUid);
  }

  await db.collection(NOTIFICATIONS_LOG).add({
    offerId,
    productName: offer.productName,
    title,
    body,
    recipientCount: recipients.length,
    successCount,
    failureCount,
    sentAt: FieldValue.serverTimestamp(),
  });

  logger.info('Offer notification sent', {
    offerId,
    recipientCount: recipients.length,
    successCount,
    failureCount,
  });
  return { recipientCount: recipients.length, successCount, failureCount };
}

/** Publishing an offer = creating the document. */
export const onOfferPublished = onDocumentCreated(
  `${OFFERS}/{offerId}`,
  async (event) => {
    const snapshot = event.data;
    if (!snapshot) {
      return;
    }
    const offer = snapshot.data() as OfferDoc;
    const offerId = event.params.offerId;

    const result = await notifyStoresAboutOffer(offerId, offer);
    await snapshot.ref.update({
      notifiedAt: FieldValue.serverTimestamp(),
      notifiedCount: result.recipientCount,
    });
  },
);

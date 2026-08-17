/**
 * Push notifications.
 *
 * A Firestore listener watches for newly published offers and pushes to every
 * active store the moment one appears — the same instant behaviour the Cloud
 * Functions trigger gave, without needing the Blaze plan.
 *
 * `notifiedAt` on the offer is the guard against double-sending: an offer is
 * only ever notified when that field is null, and it is stamped immediately
 * after. That also makes restarts safe — the listener replays existing
 * documents on reconnect, and already-notified ones are skipped.
 */
import { FieldValue, type QueryDocumentSnapshot } from 'firebase-admin/firestore';
import type { MulticastMessage } from 'firebase-admin/messaging';

import { db, messaging, NOTIFICATIONS_LOG, OFFERS, USERS } from './firebase';

/** FCM rejects multicasts larger than this. */
const MULTICAST_BATCH_SIZE = 500;

const DEAD_TOKEN_CODES = new Set([
  'messaging/registration-token-not-registered',
  'messaging/invalid-registration-token',
  'messaging/invalid-argument',
]);

/** Offers currently being sent, so a re-fired snapshot cannot double-send. */
const inFlight = new Set<string>();

interface TokenOwner {
  uid: string;
  token: string;
}

async function activeStoreTokens(): Promise<TokenOwner[]> {
  const snapshot = await db()
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
  await Promise.all(
    [...deadTokensByUid].map(([uid, tokens]) =>
      db()
        .collection(USERS)
        .doc(uid)
        .update({ fcmTokens: FieldValue.arrayRemove(...tokens) })
        .catch((error) =>
          console.warn(`[push] could not prune tokens for ${uid}:`, error),
        ),
    ),
  );
}

export async function notifyStoresAboutOffer(
  offerId: string,
  offer: FirebaseFirestore.DocumentData,
): Promise<void> {
  const recipients = await activeStoreTokens();
  const title = `New bonus offer: ${offer.productName}`;
  const body = `Buy ${offer.buyQty} Get ${offer.freeQty} Free — valid until ${offer.expiryDate}`;

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
        productName: String(offer.productName ?? ''),
        expiryDate: String(offer.expiryDate ?? ''),
      },
      android: {
        priority: 'high',
        notification: {
          channelId: 'bonus_offers',
          clickAction: 'OPEN_OFFER_DETAIL',
        },
      },
    };

    const response = await messaging().sendEachForMulticast(message);
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
        console.warn(`[push] delivery failed for ${uid}: ${code}`);
      }
    });
  }

  if (deadTokensByUid.size > 0) {
    await pruneTokens(deadTokensByUid);
  }

  await db().collection(NOTIFICATIONS_LOG).add({
    offerId,
    productName: offer.productName,
    title,
    body,
    recipientCount: recipients.length,
    successCount,
    failureCount,
    sentAt: FieldValue.serverTimestamp(),
  });

  console.log(
    `[push] offer ${offerId}: ${successCount}/${recipients.length} delivered` +
      (failureCount > 0 ? `, ${failureCount} failed` : ''),
  );
}

async function handleNewOffer(doc: QueryDocumentSnapshot): Promise<void> {
  if (inFlight.has(doc.id)) {
    return;
  }
  inFlight.add(doc.id);
  try {
    // Claim the offer first: stamping notifiedAt before sending means a crash
    // mid-send cannot turn into a second notification on restart.
    await doc.ref.update({ notifiedAt: FieldValue.serverTimestamp() });
    await notifyStoresAboutOffer(doc.id, doc.data());
    const recipients = await db()
      .collection(NOTIFICATIONS_LOG)
      .where('offerId', '==', doc.id)
      .limit(1)
      .get();
    const count = recipients.empty ? 0 : recipients.docs[0].get('recipientCount');
    await doc.ref.update({ notifiedCount: count ?? 0 });
  } catch (error) {
    console.error(`[push] failed to notify for offer ${doc.id}:`, error);
  } finally {
    inFlight.delete(doc.id);
  }
}

/** Starts watching for newly published offers. Returns an unsubscribe function. */
export function watchForNewOffers(): () => void {
  console.log('[push] watching for new offers');
  return db()
    .collection(OFFERS)
    .where('notifiedAt', '==', null)
    .onSnapshot(
      (snapshot) => {
        for (const change of snapshot.docChanges()) {
          if (change.type === 'added') {
            void handleNewOffer(change.doc);
          }
        }
      },
      (error) => {
        console.error('[push] offer listener error:', error);
      },
    );
}

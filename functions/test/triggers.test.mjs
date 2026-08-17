/**
 * Firestore trigger tests: publishing an offer logs a notification, and
 * editing an offer's expiry date re-stamps its status.
 *
 * Run with: npm run test:triggers
 */
import assert from 'node:assert/strict';
import { after, before, test } from 'node:test';

process.env.GCLOUD_PROJECT ??= 'demo-pharmacy';
process.env.FIRESTORE_EMULATOR_HOST ??= '127.0.0.1:8080';

const { initializeApp } = await import('firebase-admin/app');
const { getFirestore } = await import('firebase-admin/firestore');

initializeApp({ projectId: process.env.GCLOUD_PROJECT });
const db = getFirestore();

const OFFERS = 'bonusOffers';
const LOG = 'notificationsLog';

/** Triggers are asynchronous; poll until the effect lands or we give up. */
async function eventually(check, { timeoutMs = 15_000, intervalMs = 250 } = {}) {
  const deadline = Date.now() + timeoutMs;
  let lastValue;
  while (Date.now() < deadline) {
    lastValue = await check();
    if (lastValue) {
      return lastValue;
    }
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }
  throw new Error('Timed out waiting for the trigger to run');
}

async function clearAll() {
  for (const name of [OFFERS, LOG]) {
    const snapshot = await db.collection(name).get();
    await Promise.all(snapshot.docs.map((doc) => doc.ref.delete()));
  }
}

function offerData(overrides = {}) {
  return {
    productName: 'Brufen 400mg',
    buyQty: 10,
    freeQty: 2,
    startDate: '2026-08-01',
    expiryDate: '2099-12-31',
    status: 'active',
    createdBy: 'admin-1',
    notifiedAt: null,
    createdAt: new Date(),
    updatedAt: new Date(),
    ...overrides,
  };
}

before(clearAll);
after(clearAll);

test('publishing an offer writes a notification log entry and stamps the offer', async () => {
  const ref = await db.collection(OFFERS).add(offerData());

  const logEntry = await eventually(async () => {
    const snapshot = await db.collection(LOG).where('offerId', '==', ref.id).get();
    return snapshot.empty ? null : snapshot.docs[0];
  });

  assert.equal(logEntry.get('productName'), 'Brufen 400mg');
  assert.match(logEntry.get('title'), /New bonus offer: Brufen 400mg/);
  assert.match(logEntry.get('body'), /Buy 10 Get 2 Free/);
  // No store owners exist in this run, so nobody was messaged.
  assert.equal(logEntry.get('recipientCount'), 0);
  assert.ok(logEntry.get('sentAt'));

  const stamped = await eventually(async () => {
    const snapshot = await ref.get();
    return snapshot.get('notifiedAt') ? snapshot : null;
  });
  assert.equal(stamped.get('notifiedCount'), 0);
});

test('editing the expiry date re-stamps the status server-side', async () => {
  const ref = await db.collection(OFFERS).add(offerData({ productName: 'Calpol' }));
  await eventually(async () => (await ref.get()).get('notifiedAt'));

  // Pretend the admin corrected the expiry date to one already in the past.
  await ref.update({ expiryDate: '2020-01-01' });

  const corrected = await eventually(async () => {
    const snapshot = await ref.get();
    return snapshot.get('status') === 'expired' ? snapshot : null;
  });
  assert.equal(corrected.get('status'), 'expired');
});

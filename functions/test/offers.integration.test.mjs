/**
 * Integration test for the daily expiry job, run against the Firestore
 * emulator with the real Admin SDK.
 *
 * Run with: npm run test:integration
 */
import assert from 'node:assert/strict';
import { after, before, beforeEach, test } from 'node:test';

process.env.GCLOUD_PROJECT ??= 'demo-pharmacy';
process.env.FIRESTORE_EMULATOR_HOST ??= '127.0.0.1:8080';

const { refreshOfferStatuses } = await import('../lib/offers.js');
const { db } = await import('../lib/firebase.js');

const OFFERS = 'bonusOffers';

function offer(id, expiryDate, status) {
  return {
    id,
    data: {
      productName: `Product ${id}`,
      buyQty: 5,
      freeQty: 1,
      startDate: '2026-01-01',
      expiryDate,
      status,
      createdBy: 'admin-1',
      createdAt: new Date('2026-01-01T00:00:00Z'),
    },
  };
}

async function clearOffers() {
  const snapshot = await db.collection(OFFERS).get();
  await Promise.all(snapshot.docs.map((doc) => doc.ref.delete()));
}

async function seed(offers) {
  await Promise.all(
    offers.map(({ id, data }) => db.collection(OFFERS).doc(id).set(data)),
  );
}

async function statusOf(id) {
  return (await db.collection(OFFERS).doc(id).get()).get('status');
}

before(clearOffers);
after(clearOffers);
beforeEach(clearOffers);

test('flips offers to expiring_soon and expired for the given day', async () => {
  await seed([
    offer('far', '2026-12-31', 'active'),
    offer('soon', '2026-08-19', 'active'),
    offer('today', '2026-08-17', 'active'),
    offer('past', '2026-08-10', 'active'),
  ]);

  const result = await refreshOfferStatuses('2026-08-17');

  assert.equal(result.scanned, 4);
  assert.equal(result.updated, 3);
  assert.equal(await statusOf('far'), 'active');
  assert.equal(await statusOf('soon'), 'expiring_soon');
  assert.equal(await statusOf('today'), 'expiring_soon');
  assert.equal(await statusOf('past'), 'expired');
});

test('writes nothing when every status is already correct', async () => {
  await seed([
    offer('far', '2026-12-31', 'active'),
    offer('past', '2026-08-10', 'expired'),
  ]);

  const result = await refreshOfferStatuses('2026-08-17');

  assert.equal(result.updated, 0);
});

test('an offer whose expiry date is unusable is skipped, not crashed on', async () => {
  await seed([offer('broken', 'not-a-date', 'active'), offer('past', '2026-01-05', 'active')]);

  const result = await refreshOfferStatuses('2026-08-17');

  assert.equal(result.updated, 1);
  assert.equal(await statusOf('broken'), 'active');
  assert.equal(await statusOf('past'), 'expired');
});

test('handles more offers than fit in one write batch', async () => {
  const many = Array.from({ length: 450 }, (_, index) =>
    offer(`bulk-${index}`, '2026-08-01', 'active'),
  );
  await seed(many);

  const result = await refreshOfferStatuses('2026-08-17');

  assert.equal(result.updated, 450);
  assert.equal(await statusOf('bulk-0'), 'expired');
  assert.equal(await statusOf('bulk-449'), 'expired');
});

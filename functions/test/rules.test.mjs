/**
 * Firestore security rules tests.
 *
 * Run with: npm run test:rules   (starts the Firestore emulator itself)
 */
import assert from 'node:assert/strict';
import { after, before, beforeEach, test } from 'node:test';
import { readFileSync } from 'node:fs';

import {
  assertFails,
  assertSucceeds,
  initializeTestEnvironment,
} from '@firebase/rules-unit-testing';
import {
  addDoc,
  collection,
  deleteDoc,
  doc,
  getDoc,
  getDocs,
  setDoc,
  updateDoc,
} from 'firebase/firestore';

const ADMIN_UID = 'admin-1';
const STORE_UID = 'store-1';
const OTHER_STORE_UID = 'store-2';

let testEnv;

const adminDb = () =>
  testEnv.authenticatedContext(ADMIN_UID, { role: 'admin' }).firestore();
const storeDb = (uid = STORE_UID) =>
  testEnv.authenticatedContext(uid, { role: 'store_owner' }).firestore();
const anonDb = () => testEnv.unauthenticatedContext().firestore();

function offer(overrides = {}) {
  return {
    productName: 'Panadol 500mg',
    buyQty: 5,
    freeQty: 1,
    startDate: '2026-08-01',
    expiryDate: '2026-09-30',
    status: 'active',
    createdBy: ADMIN_UID,
    notifiedAt: null,
    ...overrides,
  };
}

before(async () => {
  testEnv = await initializeTestEnvironment({
    projectId: 'demo-pharmacy',
    firestore: {
      rules: readFileSync(new URL('../../firestore.rules', import.meta.url), 'utf8'),
      host: '127.0.0.1',
      port: 8080,
    },
  });
});

after(async () => {
  await testEnv?.cleanup();
});

beforeEach(async () => {
  await testEnv.clearFirestore();
  await testEnv.withSecurityRulesDisabled(async (context) => {
    const db = context.firestore();
    await setDoc(doc(db, 'users', STORE_UID), {
      role: 'store_owner',
      username: 'alshifa',
      storeName: 'Al-Shifa Medical Store',
      isActive: true,
      fcmTokens: ['token-a'],
    });
    await setDoc(doc(db, 'users', OTHER_STORE_UID), {
      role: 'store_owner',
      username: 'noor',
      storeName: 'Noor Medical Store',
      isActive: true,
      fcmTokens: [],
    });
    await setDoc(doc(db, 'users', ADMIN_UID), { role: 'admin', username: 'owner' });
    await setDoc(doc(db, 'bonusOffers', 'offer-1'), offer());
    await setDoc(doc(db, 'notificationsLog', 'log-1'), {
      offerId: 'offer-1',
      recipientCount: 2,
    });
  });
});

test('a store owner can read offers', async () => {
  await assertSucceeds(getDocs(collection(storeDb(), 'bonusOffers')));
});

test('a store owner cannot create, edit or delete offers', async () => {
  const db = storeDb();
  await assertFails(addDoc(collection(db, 'bonusOffers'), offer()));
  await assertFails(updateDoc(doc(db, 'bonusOffers', 'offer-1'), { buyQty: 1 }));
  await assertFails(deleteDoc(doc(db, 'bonusOffers', 'offer-1')));
});

test('a store owner reads its own profile but not another store', async () => {
  await assertSucceeds(getDoc(doc(storeDb(), 'users', STORE_UID)));
  await assertFails(getDoc(doc(storeDb(), 'users', OTHER_STORE_UID)));
});

test('a store owner may write only its own push tokens', async () => {
  await assertSucceeds(
    updateDoc(doc(storeDb(), 'users', STORE_UID), { fcmTokens: ['token-a', 'token-b'] }),
  );
  await assertFails(
    updateDoc(doc(storeDb(), 'users', STORE_UID), { storeName: 'Renamed by store' }),
  );
  await assertFails(
    updateDoc(doc(storeDb(), 'users', STORE_UID), { isActive: false }),
  );
  await assertFails(
    updateDoc(doc(storeDb(), 'users', OTHER_STORE_UID), { fcmTokens: ['stolen'] }),
  );
});

test('a store owner cannot read the notification log', async () => {
  await assertFails(getDoc(doc(storeDb(), 'notificationsLog', 'log-1')));
});

test('signed-out visitors see nothing', async () => {
  await assertFails(getDocs(collection(anonDb(), 'bonusOffers')));
  await assertFails(getDoc(doc(anonDb(), 'users', STORE_UID)));
});

test('an admin publishes, edits and deletes offers', async () => {
  const db = adminDb();
  await assertSucceeds(addDoc(collection(db, 'bonusOffers'), offer()));
  await assertSucceeds(
    setDoc(doc(db, 'bonusOffers', 'offer-1'), offer({ buyQty: 10 })),
  );
  await assertSucceeds(deleteDoc(doc(db, 'bonusOffers', 'offer-1')));
});

test('malformed offers are rejected even from an admin', async () => {
  const db = adminDb();
  const offers = collection(db, 'bonusOffers');
  await assertFails(addDoc(offers, offer({ productName: '' })));
  await assertFails(addDoc(offers, offer({ buyQty: 0 })));
  await assertFails(addDoc(offers, offer({ freeQty: -1 })));
  await assertFails(addDoc(offers, offer({ buyQty: 2.5 })));
  await assertFails(addDoc(offers, offer({ expiryDate: '30-09-2026' })));
  // Expiry before start.
  await assertFails(
    addDoc(offers, offer({ startDate: '2026-09-30', expiryDate: '2026-08-01' })),
  );
  await assertFails(addDoc(offers, offer({ status: 'draft' })));
  // createdBy must be the admin actually writing it.
  await assertFails(addDoc(offers, offer({ createdBy: STORE_UID })));
});

test('an admin reads users and the notification log but cannot forge log entries', async () => {
  const db = adminDb();
  await assertSucceeds(getDoc(doc(db, 'users', STORE_UID)));
  await assertSucceeds(getDoc(doc(db, 'notificationsLog', 'log-1')));
  await assertFails(
    addDoc(collection(db, 'notificationsLog'), { offerId: 'offer-1', recipientCount: 99 }),
  );
});

test('nobody creates or deletes user documents from a client', async () => {
  await assertFails(
    setDoc(doc(adminDb(), 'users', 'made-up-uid'), { role: 'store_owner' }),
  );
  await assertFails(deleteDoc(doc(adminDb(), 'users', STORE_UID)));
});

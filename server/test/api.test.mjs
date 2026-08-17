/**
 * End-to-end test of the VPS server against the Firebase emulators.
 *
 * Boots the real compiled server, then drives it exactly as the dashboard
 * does: sign in with Firebase Auth, send the ID token, call the API.
 *
 * Run with: npm run test:e2e
 */
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { after, before, test } from 'node:test';

const PROJECT_ID = 'demo-pharmacy';
const PORT = 8099;
const BASE = `http://127.0.0.1:${PORT}`;
const AUTH_EMULATOR = '127.0.0.1:9099';
const ADMIN_EMAIL = 'owner@example.com';
const ADMIN_PASSWORD = 'admin-password';

process.env.GCLOUD_PROJECT ??= PROJECT_ID;
process.env.FIRESTORE_EMULATOR_HOST ??= '127.0.0.1:8080';
process.env.FIREBASE_AUTH_EMULATOR_HOST ??= AUTH_EMULATOR;

const { initializeApp } = await import('firebase-admin/app');
const { getAuth } = await import('firebase-admin/auth');
const { getFirestore } = await import('firebase-admin/firestore');

initializeApp({ projectId: PROJECT_ID });
const adminAuth = getAuth();
const db = getFirestore();

let serverProcess;
let adminToken;

/** Signs in through the Auth emulator's REST API, like the browser would. */
async function signIn(email, password) {
  const response = await fetch(
    `http://${AUTH_EMULATOR}/identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=fake-api-key`,
    {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ email, password, returnSecureToken: true }),
    },
  );
  const body = await response.json();
  if (!response.ok) {
    throw new Error(`sign-in failed: ${JSON.stringify(body)}`);
  }
  return body.idToken;
}

function api(path, { token, method = 'GET', body } = {}) {
  return fetch(`${BASE}${path}`, {
    method,
    headers: {
      ...(body ? { 'content-type': 'application/json' } : {}),
      ...(token ? { authorization: `Bearer ${token}` } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
}

async function waitFor(check, { timeoutMs = 20_000, intervalMs = 250 } = {}) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const value = await check().catch(() => null);
    if (value) return value;
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }
  throw new Error('timed out waiting for the server');
}

before(async () => {
  // Clean slate.
  for (const name of ['users', 'bonusOffers', 'notificationsLog']) {
    const snapshot = await db.collection(name).get();
    await Promise.all(snapshot.docs.map((doc) => doc.ref.delete()));
  }

  const admin = await adminAuth.createUser({
    email: ADMIN_EMAIL,
    password: ADMIN_PASSWORD,
  });
  await adminAuth.setCustomUserClaims(admin.uid, { role: 'admin' });
  await db.collection('users').doc(admin.uid).set({
    role: 'admin',
    username: 'owner',
    isActive: true,
  });

  serverProcess = spawn('node', ['dist/index.js'], {
    env: {
      ...process.env,
      FIREBASE_PROJECT_ID: PROJECT_ID,
      FIREBASE_API_KEY: 'fake-api-key',
      FIREBASE_MESSAGING_SENDER_ID: '000000000000',
      FIREBASE_APP_ID: '1:000000000000:web:abcdef',
      PORT: String(PORT),
      HOST: '127.0.0.1',
      STATIC_DIR: '../web/dist',
    },
    stdio: 'inherit',
  });

  await waitFor(async () => (await api('/api/health')).ok);
  adminToken = await signIn(ADMIN_EMAIL, ADMIN_PASSWORD);
});

after(() => {
  serverProcess?.kill('SIGTERM');
});

test('serves the Firebase web config to the dashboard', async () => {
  const response = await api('/api/config');
  assert.equal(response.status, 200);
  const config = await response.json();
  assert.equal(config.projectId, PROJECT_ID);
  assert.equal(config.apiKey, 'fake-api-key');
  // Defaults are derived from the project id.
  assert.equal(config.authDomain, `${PROJECT_ID}.firebaseapp.com`);
});

test('rejects account management without a valid admin token', async () => {
  const body = { storeName: 'Rogue', username: 'rogue', password: 'password' };

  assert.equal((await api('/api/stores', { method: 'POST', body })).status, 401);
  assert.equal(
    (await api('/api/stores', { method: 'POST', body, token: 'not-a-token' })).status,
    401,
  );

  // A store owner's own token is not enough either.
  const store = await adminAuth.createUser({
    email: 'shop@stores.10percentpharmacy.local',
    password: 'store-password',
  });
  await adminAuth.setCustomUserClaims(store.uid, { role: 'store_owner' });
  const storeToken = await signIn('shop@stores.10percentpharmacy.local', 'store-password');
  assert.equal(
    (await api('/api/stores', { method: 'POST', body, token: storeToken })).status,
    403,
  );
});

test('creates a store owner that can then log in', async () => {
  const response = await api('/api/stores', {
    method: 'POST',
    token: adminToken,
    body: {
      storeName: 'Al-Shifa Medical Store',
      ownerName: 'Store Owner',
      phone: '03001234567',
      address: 'Main Bazaar, Kahror Pakka',
      username: 'alshifa',
      password: 'store-password',
    },
  });
  assert.equal(response.status, 200);
  const { uid } = await response.json();

  const profile = await db.collection('users').doc(uid).get();
  assert.equal(profile.get('role'), 'store_owner');
  assert.equal(profile.get('storeName'), 'Al-Shifa Medical Store');
  assert.equal(profile.get('isActive'), true);
  assert.deepEqual(profile.get('fcmTokens'), []);

  const authUser = await adminAuth.getUser(uid);
  assert.equal(authUser.customClaims.role, 'store_owner');

  // The store signs in with its username, mapped to the alias email.
  const token = await signIn('alshifa@stores.10percentpharmacy.local', 'store-password');
  assert.ok(token.length > 0);
});

test('rejects duplicates and invalid input with readable messages', async () => {
  const post = (body) => api('/api/stores', { method: 'POST', token: adminToken, body });

  const duplicate = await post({
    storeName: 'Copycat',
    username: 'alshifa',
    password: 'another-password',
  });
  assert.equal(duplicate.status, 409);
  assert.match((await duplicate.json()).error, /already taken/);

  assert.equal((await post({ storeName: 'X', username: 'Bad Name!', password: 'password' })).status, 400);
  assert.equal((await post({ storeName: 'X', username: 'shortpw', password: '123' })).status, 400);
  assert.equal((await post({ storeName: '', username: 'nostore', password: 'password' })).status, 400);
});

test('edits details and resets the password', async () => {
  const created = await (
    await api('/api/stores', {
      method: 'POST',
      token: adminToken,
      body: { storeName: 'Noor Medical Store', username: 'noor', password: 'first-password' },
    })
  ).json();

  const response = await api(`/api/stores/${created.uid}`, {
    method: 'PATCH',
    token: adminToken,
    body: {
      storeName: 'Noor Medical Store & Clinic',
      ownerName: 'Noor Ahmed',
      phone: '03007654321',
      address: '',
      password: 'second-password',
    },
  });
  assert.equal(response.status, 200);

  const profile = await db.collection('users').doc(created.uid).get();
  assert.equal(profile.get('storeName'), 'Noor Medical Store & Clinic');
  assert.equal(profile.get('address'), null);
  assert.equal(profile.get('username'), 'noor', 'username must survive an edit');

  await assert.rejects(() =>
    signIn('noor@stores.10percentpharmacy.local', 'first-password'),
  );
  assert.ok(await signIn('noor@stores.10percentpharmacy.local', 'second-password'));
});

test('deactivating blocks login and clears push tokens', async () => {
  const created = await (
    await api('/api/stores', {
      method: 'POST',
      token: adminToken,
      body: { storeName: 'Closing Store', username: 'closing', password: 'store-password' },
    })
  ).json();
  await db.collection('users').doc(created.uid).update({ fcmTokens: ['token-a', 'token-b'] });

  const off = await api(`/api/stores/${created.uid}/active`, {
    method: 'POST',
    token: adminToken,
    body: { isActive: false },
  });
  assert.equal(off.status, 200);

  const profile = await db.collection('users').doc(created.uid).get();
  assert.equal(profile.get('isActive'), false);
  assert.deepEqual(profile.get('fcmTokens'), []);
  assert.equal((await adminAuth.getUser(created.uid)).disabled, true);
  await assert.rejects(() =>
    signIn('closing@stores.10percentpharmacy.local', 'store-password'),
  );

  // Reactivating restores access with the same password.
  const on = await api(`/api/stores/${created.uid}/active`, {
    method: 'POST',
    token: adminToken,
    body: { isActive: true },
  });
  assert.equal(on.status, 200);
  assert.ok(await signIn('closing@stores.10percentpharmacy.local', 'store-password'));
});

test('publishing an offer notifies the stores and logs it', async () => {
  const ref = await db.collection('bonusOffers').add({
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
  });

  const logEntry = await waitFor(async () => {
    const snapshot = await db
      .collection('notificationsLog')
      .where('offerId', '==', ref.id)
      .get();
    return snapshot.empty ? null : snapshot.docs[0];
  });

  assert.match(logEntry.get('title'), /New bonus offer: Brufen 400mg/);
  assert.match(logEntry.get('body'), /Buy 10 Get 2 Free/);
  // No devices are registered in this run, so nobody was messaged.
  assert.equal(logEntry.get('recipientCount'), 0);

  const stamped = await waitFor(async () => {
    const snapshot = await ref.get();
    return snapshot.get('notifiedAt') ? snapshot : null;
  });
  assert.ok(stamped.get('notifiedAt'));

  // Exactly one notification per offer, even though the listener re-fires.
  await new Promise((resolve) => setTimeout(resolve, 1500));
  const allLogs = await db
    .collection('notificationsLog')
    .where('offerId', '==', ref.id)
    .get();
  assert.equal(allLogs.size, 1, 'an offer must never be notified twice');
});

test('corrects the status when an expiry date is edited', async () => {
  const ref = await db.collection('bonusOffers').add({
    productName: 'Calpol',
    buyQty: 5,
    freeQty: 1,
    startDate: '2026-01-01',
    expiryDate: '2099-12-31',
    status: 'active',
    createdBy: 'admin-1',
    notifiedAt: new Date(),
    createdAt: new Date(),
    updatedAt: new Date(),
  });

  await ref.update({ expiryDate: '2020-01-01' });

  const corrected = await waitFor(async () => {
    const snapshot = await ref.get();
    return snapshot.get('status') === 'expired' ? snapshot : null;
  });
  assert.equal(corrected.get('status'), 'expired');
});

test('the admin can force a status re-check from the dashboard', async () => {
  const response = await api('/api/offers/refresh-status', {
    method: 'POST',
    token: adminToken,
  });
  assert.equal(response.status, 200);
  const result = await response.json();
  assert.ok(result.scanned >= 1);
  assert.equal(typeof result.updated, 'number');
});

/**
 * End-to-end test of the store owner management callables against the Auth,
 * Firestore and Functions emulators.
 *
 * Run with: npm run test:callables
 */
import assert from 'node:assert/strict';
import { after, before, test } from 'node:test';

process.env.GCLOUD_PROJECT ??= 'demo-pharmacy';
process.env.FIRESTORE_EMULATOR_HOST ??= '127.0.0.1:8080';
process.env.FIREBASE_AUTH_EMULATOR_HOST ??= '127.0.0.1:9099';

const PROJECT_ID = process.env.GCLOUD_PROJECT;
const REGION = 'asia-south1';
const ADMIN_EMAIL = 'owner@example.com';
const ADMIN_PASSWORD = 'admin-password';

const { initializeApp: initAdminApp } = await import('firebase-admin/app');
const { getAuth: getAdminAuth } = await import('firebase-admin/auth');
const { getFirestore: getAdminFirestore } = await import('firebase-admin/firestore');

const { initializeApp } = await import('firebase/app');
const {
  connectAuthEmulator,
  getAuth,
  signInWithEmailAndPassword,
  signOut,
} = await import('firebase/auth');
const { connectFunctionsEmulator, getFunctions, httpsCallable } = await import(
  'firebase/functions'
);

initAdminApp({ projectId: PROJECT_ID });
const adminAuth = getAdminAuth();
const adminDb = getAdminFirestore();

const clientApp = initializeApp({ projectId: PROJECT_ID, apiKey: 'fake-api-key' });
const clientAuth = getAuth(clientApp);
connectAuthEmulator(clientAuth, 'http://127.0.0.1:9099', { disableWarnings: true });
const functions = getFunctions(clientApp, REGION);
connectFunctionsEmulator(functions, '127.0.0.1', 5001);

const createStoreOwner = httpsCallable(functions, 'createStoreOwner');
const updateStoreOwner = httpsCallable(functions, 'updateStoreOwner');
const setStoreOwnerActive = httpsCallable(functions, 'setStoreOwnerActive');

async function signInAsAdmin() {
  await signInWithEmailAndPassword(clientAuth, ADMIN_EMAIL, ADMIN_PASSWORD);
}

async function errorCodeOf(promise) {
  try {
    await promise;
    return null;
  } catch (error) {
    return error.code ?? String(error);
  }
}

before(async () => {
  const admin = await adminAuth.createUser({
    email: ADMIN_EMAIL,
    password: ADMIN_PASSWORD,
  });
  await adminAuth.setCustomUserClaims(admin.uid, { role: 'admin' });
  await adminDb.collection('users').doc(admin.uid).set({
    role: 'admin',
    username: 'owner',
    isActive: true,
  });
  await signInAsAdmin();
});

after(async () => {
  await signOut(clientAuth);
});

test('an admin creates a store owner that can then log in', async () => {
  const result = await createStoreOwner({
    storeName: 'Al-Shifa Medical Store',
    ownerName: 'Store Owner',
    phone: '03001234567',
    address: 'Main Bazaar, Kahror Pakka',
    username: 'alshifa',
    password: 'store-password',
  });

  const uid = result.data.uid;
  const profile = await adminDb.collection('users').doc(uid).get();
  assert.equal(profile.get('role'), 'store_owner');
  assert.equal(profile.get('username'), 'alshifa');
  assert.equal(profile.get('storeName'), 'Al-Shifa Medical Store');
  assert.equal(profile.get('isActive'), true);
  assert.deepEqual(profile.get('fcmTokens'), []);

  const authUser = await adminAuth.getUser(uid);
  assert.equal(authUser.customClaims.role, 'store_owner');
  assert.equal(authUser.disabled, false);

  // The store signs in with its username, mapped to the alias email.
  const credential = await signInWithEmailAndPassword(
    clientAuth,
    'alshifa@stores.10percentpharmacy.local',
    'store-password',
  );
  assert.equal(credential.user.uid, uid);
  await signInAsAdmin();
});

test('duplicate usernames and weak input are rejected', async () => {
  assert.equal(
    await errorCodeOf(
      createStoreOwner({
        storeName: 'Copycat Store',
        username: 'alshifa',
        password: 'another-password',
      }),
    ),
    'functions/already-exists',
  );

  assert.equal(
    await errorCodeOf(
      createStoreOwner({ storeName: 'X', username: 'Bad Name!', password: 'password' }),
    ),
    'functions/invalid-argument',
  );

  assert.equal(
    await errorCodeOf(
      createStoreOwner({ storeName: 'X', username: 'shortpw', password: '123' }),
    ),
    'functions/invalid-argument',
  );

  assert.equal(
    await errorCodeOf(
      createStoreOwner({ storeName: '', username: 'nostore', password: 'password' }),
    ),
    'functions/invalid-argument',
  );
});

test('editing a store updates details and can reset the password', async () => {
  const created = await createStoreOwner({
    storeName: 'Noor Medical Store',
    username: 'noor',
    password: 'first-password',
  });
  const uid = created.data.uid;

  await updateStoreOwner({
    uid,
    storeName: 'Noor Medical Store & Clinic',
    ownerName: 'Noor Ahmed',
    phone: '03007654321',
    address: '',
    password: 'second-password',
  });

  const profile = await adminDb.collection('users').doc(uid).get();
  assert.equal(profile.get('storeName'), 'Noor Medical Store & Clinic');
  assert.equal(profile.get('ownerName'), 'Noor Ahmed');
  assert.equal(profile.get('address'), null);
  // The username is not editable, so it must survive the update untouched.
  assert.equal(profile.get('username'), 'noor');

  const email = 'noor@stores.10percentpharmacy.local';
  // Production reports a bad password as auth/invalid-credential; the emulator
  // still uses the older auth/wrong-password. Both mean "rejected".
  assert.ok(
    ['auth/invalid-credential', 'auth/wrong-password'].includes(
      await errorCodeOf(signInWithEmailAndPassword(clientAuth, email, 'first-password')),
    ),
  );
  await signInWithEmailAndPassword(clientAuth, email, 'second-password');
  await signInAsAdmin();
});

test('deactivating a store blocks its login and clears its push tokens', async () => {
  const created = await createStoreOwner({
    storeName: 'Closing Store',
    username: 'closing',
    password: 'store-password',
  });
  const uid = created.data.uid;
  await adminDb.collection('users').doc(uid).update({ fcmTokens: ['token-a', 'token-b'] });

  await setStoreOwnerActive({ uid, isActive: false });

  const profile = await adminDb.collection('users').doc(uid).get();
  assert.equal(profile.get('isActive'), false);
  assert.deepEqual(profile.get('fcmTokens'), []);
  assert.equal((await adminAuth.getUser(uid)).disabled, true);

  const email = 'closing@stores.10percentpharmacy.local';
  assert.equal(
    await errorCodeOf(signInWithEmailAndPassword(clientAuth, email, 'store-password')),
    'auth/user-disabled',
  );

  // Reactivating restores access with the same password.
  await signInAsAdmin();
  await setStoreOwnerActive({ uid, isActive: true });
  assert.equal((await adminAuth.getUser(uid)).disabled, false);
  await signInWithEmailAndPassword(clientAuth, email, 'store-password');
  await signInAsAdmin();
});

test('a store owner cannot manage accounts, and neither can a signed-out caller', async () => {
  await signInWithEmailAndPassword(
    clientAuth,
    'alshifa@stores.10percentpharmacy.local',
    'store-password',
  );
  assert.equal(
    await errorCodeOf(
      createStoreOwner({ storeName: 'Rogue', username: 'rogue', password: 'password' }),
    ),
    'functions/permission-denied',
  );
  assert.equal(
    await errorCodeOf(setStoreOwnerActive({ uid: 'whoever', isActive: false })),
    'functions/permission-denied',
  );

  await signOut(clientAuth);
  assert.equal(
    await errorCodeOf(
      createStoreOwner({ storeName: 'Rogue', username: 'rogue2', password: 'password' }),
    ),
    'functions/unauthenticated',
  );

  await signInAsAdmin();
});

test('editing an unknown store id is refused', async () => {
  assert.equal(
    await errorCodeOf(updateStoreOwner({ uid: 'does-not-exist', storeName: 'Ghost' })),
    'functions/not-found',
  );
});

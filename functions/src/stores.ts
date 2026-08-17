/**
 * Store owner account management.
 *
 * There is no self-registration: every account is created here by the admin.
 * Creating and disabling Firebase Auth users needs the Admin SDK, so these are
 * callable functions rather than direct writes from the dashboard.
 */
import { FieldValue } from 'firebase-admin/firestore';
import { HttpsError, onCall } from 'firebase-functions/v2/https';
import { logger } from 'firebase-functions';

import { auth, db, USERS } from './firebase';
import {
  optionalString,
  requireAdmin,
  requirePassword,
  requirePhone,
  requireString,
  requireUsername,
} from './guards';
import { usernameToEmail } from './types';

interface StoreOwnerInput {
  storeName?: unknown;
  ownerName?: unknown;
  phone?: unknown;
  address?: unknown;
  username?: unknown;
  password?: unknown;
  uid?: unknown;
  isActive?: unknown;
}

export const createStoreOwner = onCall<StoreOwnerInput>(async (request) => {
  const adminUid = requireAdmin(request);
  const data = request.data ?? {};

  const storeName = requireString(data.storeName, 'Store name', { max: 120 });
  const ownerName = optionalString(data.ownerName, 'Owner name', 120);
  const phone = requirePhone(data.phone);
  const address = optionalString(data.address, 'Address', 300);
  const username = requireUsername(data.username);
  const password = requirePassword(data.password);

  const existing = await db
    .collection(USERS)
    .where('username', '==', username)
    .limit(1)
    .get();
  if (!existing.empty) {
    throw new HttpsError('already-exists', `Username "${username}" is already taken.`);
  }

  let userRecord;
  try {
    userRecord = await auth.createUser({
      email: usernameToEmail(username),
      password,
      displayName: storeName,
      disabled: false,
    });
  } catch (error) {
    const code = (error as { code?: string }).code;
    if (code === 'auth/email-already-exists') {
      throw new HttpsError('already-exists', `Username "${username}" is already taken.`);
    }
    logger.error('createUser failed', error);
    throw new HttpsError('internal', 'Could not create the login for this store.');
  }

  await auth.setCustomUserClaims(userRecord.uid, { role: 'store_owner' });

  const now = FieldValue.serverTimestamp();
  await db.collection(USERS).doc(userRecord.uid).set({
    role: 'store_owner',
    username,
    storeName,
    ownerName,
    phone,
    address,
    isActive: true,
    fcmTokens: [],
    createdBy: adminUid,
    createdAt: now,
    updatedAt: now,
  });

  logger.info('Store owner created', { uid: userRecord.uid, username });
  return { uid: userRecord.uid, username };
});

export const updateStoreOwner = onCall<StoreOwnerInput>(async (request) => {
  requireAdmin(request);
  const data = request.data ?? {};
  const uid = requireString(data.uid, 'Store id', { max: 128 });

  const docRef = db.collection(USERS).doc(uid);
  const snapshot = await docRef.get();
  if (!snapshot.exists || snapshot.get('role') !== 'store_owner') {
    throw new HttpsError('not-found', 'Store owner not found.');
  }

  const updates: Record<string, unknown> = {
    storeName: requireString(data.storeName, 'Store name', { max: 120 }),
    ownerName: optionalString(data.ownerName, 'Owner name', 120),
    phone: requirePhone(data.phone),
    address: optionalString(data.address, 'Address', 300),
    updatedAt: FieldValue.serverTimestamp(),
  };

  await docRef.update(updates);
  await auth.updateUser(uid, { displayName: updates.storeName as string });

  // Password is optional on edit — only reset it when the admin typed a new one.
  if (data.password !== undefined && data.password !== null && data.password !== '') {
    await auth.updateUser(uid, { password: requirePassword(data.password) });
    // Force existing app sessions to re-authenticate with the new password.
    await auth.revokeRefreshTokens(uid);
    logger.info('Store owner password reset', { uid });
  }

  return { uid };
});

/**
 * Activate / deactivate a store. Disabling the Auth user is what actually locks
 * a store out: its refresh tokens are revoked, so the app is signed out on its
 * next token refresh rather than staying logged in until it happens to restart.
 */
export const setStoreOwnerActive = onCall<StoreOwnerInput>(async (request) => {
  requireAdmin(request);
  const data = request.data ?? {};
  const uid = requireString(data.uid, 'Store id', { max: 128 });
  if (typeof data.isActive !== 'boolean') {
    throw new HttpsError('invalid-argument', 'isActive must be true or false.');
  }
  const isActive = data.isActive;

  const docRef = db.collection(USERS).doc(uid);
  const snapshot = await docRef.get();
  if (!snapshot.exists || snapshot.get('role') !== 'store_owner') {
    throw new HttpsError('not-found', 'Store owner not found.');
  }

  await auth.updateUser(uid, { disabled: !isActive });
  if (!isActive) {
    await auth.revokeRefreshTokens(uid);
  }

  await docRef.update({
    isActive,
    // A deactivated store should stop receiving pushes immediately.
    ...(isActive ? {} : { fcmTokens: [] }),
    updatedAt: FieldValue.serverTimestamp(),
  });

  logger.info('Store owner activation changed', { uid, isActive });
  return { uid, isActive };
});

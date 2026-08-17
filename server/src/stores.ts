/**
 * Store owner account management.
 *
 * There is no self-registration: the admin creates every account here. Creating
 * and disabling Firebase Auth users needs the Admin SDK, which is why these run
 * on the server rather than straight from the dashboard.
 */
import { FieldValue } from 'firebase-admin/firestore';
import { Router } from 'express';

import { auth, db, USERS } from './firebase';
import { requireAdmin, type AdminRequest } from './auth';
import {
  ApiError,
  optionalString,
  requirePassword,
  requirePhone,
  requireString,
  requireUsername,
  usernameToEmail,
} from './validation';

export const storesRouter = Router();

storesRouter.use(requireAdmin);

storesRouter.post('/', async (req: AdminRequest, res, next) => {
  try {
    const body = req.body ?? {};
    const storeName = requireString(body.storeName, 'Store name', { max: 120 });
    const ownerName = optionalString(body.ownerName, 'Owner name', 120);
    const phone = requirePhone(body.phone);
    const address = optionalString(body.address, 'Address', 300);
    const username = requireUsername(body.username);
    const password = requirePassword(body.password);

    const existing = await db()
      .collection(USERS)
      .where('username', '==', username)
      .limit(1)
      .get();
    if (!existing.empty) {
      throw new ApiError(409, `Username "${username}" is already taken.`);
    }

    let userRecord;
    try {
      userRecord = await auth().createUser({
        email: usernameToEmail(username),
        password,
        displayName: storeName,
        disabled: false,
      });
    } catch (error) {
      if ((error as { code?: string }).code === 'auth/email-already-exists') {
        throw new ApiError(409, `Username "${username}" is already taken.`);
      }
      throw error;
    }

    await auth().setCustomUserClaims(userRecord.uid, { role: 'store_owner' });

    const now = FieldValue.serverTimestamp();
    await db().collection(USERS).doc(userRecord.uid).set({
      role: 'store_owner',
      username,
      storeName,
      ownerName,
      phone,
      address,
      isActive: true,
      fcmTokens: [],
      createdBy: req.adminUid,
      createdAt: now,
      updatedAt: now,
    });

    console.log(`[stores] created ${username} (${userRecord.uid})`);
    res.json({ uid: userRecord.uid, username });
  } catch (error) {
    next(error);
  }
});

storesRouter.patch('/:uid', async (req, res, next) => {
  try {
    const uid = requireString(req.params.uid, 'Store id', { max: 128 });
    const body = req.body ?? {};

    const docRef = db().collection(USERS).doc(uid);
    const snapshot = await docRef.get();
    if (!snapshot.exists || snapshot.get('role') !== 'store_owner') {
      throw new ApiError(404, 'Store owner not found.');
    }

    const storeName = requireString(body.storeName, 'Store name', { max: 120 });
    await docRef.update({
      storeName,
      ownerName: optionalString(body.ownerName, 'Owner name', 120),
      phone: requirePhone(body.phone),
      address: optionalString(body.address, 'Address', 300),
      updatedAt: FieldValue.serverTimestamp(),
    });
    await auth().updateUser(uid, { displayName: storeName });

    // Password is optional on edit — only reset it when a new one was typed.
    if (body.password !== undefined && body.password !== null && body.password !== '') {
      await auth().updateUser(uid, { password: requirePassword(body.password) });
      // Force existing app sessions to re-authenticate with the new password.
      await auth().revokeRefreshTokens(uid);
      console.log(`[stores] password reset for ${uid}`);
    }

    res.json({ uid });
  } catch (error) {
    next(error);
  }
});

/**
 * Activate / deactivate a store. Disabling the Auth user is what actually locks
 * a store out: its refresh tokens are revoked, so the app is signed out on its
 * next token refresh instead of staying logged in until it restarts.
 */
storesRouter.post('/:uid/active', async (req, res, next) => {
  try {
    const uid = requireString(req.params.uid, 'Store id', { max: 128 });
    const isActive = req.body?.isActive;
    if (typeof isActive !== 'boolean') {
      throw new ApiError(400, 'isActive must be true or false.');
    }

    const docRef = db().collection(USERS).doc(uid);
    const snapshot = await docRef.get();
    if (!snapshot.exists || snapshot.get('role') !== 'store_owner') {
      throw new ApiError(404, 'Store owner not found.');
    }

    await auth().updateUser(uid, { disabled: !isActive });
    if (!isActive) {
      await auth().revokeRefreshTokens(uid);
    }

    await docRef.update({
      isActive,
      // A deactivated store should stop receiving pushes immediately.
      ...(isActive ? {} : { fcmTokens: [] }),
      updatedAt: FieldValue.serverTimestamp(),
    });

    console.log(`[stores] ${uid} isActive=${isActive}`);
    res.json({ uid, isActive });
  } catch (error) {
    next(error);
  }
});

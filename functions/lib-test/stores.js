"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.setStoreOwnerActive = exports.updateStoreOwner = exports.createStoreOwner = void 0;
/**
 * Store owner account management.
 *
 * There is no self-registration: every account is created here by the admin.
 * Creating and disabling Firebase Auth users needs the Admin SDK, so these are
 * callable functions rather than direct writes from the dashboard.
 */
const firestore_1 = require("firebase-admin/firestore");
const https_1 = require("firebase-functions/v2/https");
const firebase_functions_1 = require("firebase-functions");
const firebase_1 = require("./firebase");
const guards_1 = require("./guards");
const types_1 = require("./types");
exports.createStoreOwner = (0, https_1.onCall)(async (request) => {
    const adminUid = (0, guards_1.requireAdmin)(request);
    const data = request.data ?? {};
    const storeName = (0, guards_1.requireString)(data.storeName, 'Store name', { max: 120 });
    const ownerName = (0, guards_1.optionalString)(data.ownerName, 'Owner name', 120);
    const phone = (0, guards_1.requirePhone)(data.phone);
    const address = (0, guards_1.optionalString)(data.address, 'Address', 300);
    const username = (0, guards_1.requireUsername)(data.username);
    const password = (0, guards_1.requirePassword)(data.password);
    const existing = await firebase_1.db
        .collection(firebase_1.USERS)
        .where('username', '==', username)
        .limit(1)
        .get();
    if (!existing.empty) {
        throw new https_1.HttpsError('already-exists', `Username "${username}" is already taken.`);
    }
    let userRecord;
    try {
        userRecord = await firebase_1.auth.createUser({
            email: (0, types_1.usernameToEmail)(username),
            password,
            displayName: storeName,
            disabled: false,
        });
    }
    catch (error) {
        const code = error.code;
        if (code === 'auth/email-already-exists') {
            throw new https_1.HttpsError('already-exists', `Username "${username}" is already taken.`);
        }
        firebase_functions_1.logger.error('createUser failed', error);
        throw new https_1.HttpsError('internal', 'Could not create the login for this store.');
    }
    await firebase_1.auth.setCustomUserClaims(userRecord.uid, { role: 'store_owner' });
    const now = firestore_1.FieldValue.serverTimestamp();
    await firebase_1.db.collection(firebase_1.USERS).doc(userRecord.uid).set({
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
    firebase_functions_1.logger.info('Store owner created', { uid: userRecord.uid, username });
    return { uid: userRecord.uid, username };
});
exports.updateStoreOwner = (0, https_1.onCall)(async (request) => {
    (0, guards_1.requireAdmin)(request);
    const data = request.data ?? {};
    const uid = (0, guards_1.requireString)(data.uid, 'Store id', { max: 128 });
    const docRef = firebase_1.db.collection(firebase_1.USERS).doc(uid);
    const snapshot = await docRef.get();
    if (!snapshot.exists || snapshot.get('role') !== 'store_owner') {
        throw new https_1.HttpsError('not-found', 'Store owner not found.');
    }
    const updates = {
        storeName: (0, guards_1.requireString)(data.storeName, 'Store name', { max: 120 }),
        ownerName: (0, guards_1.optionalString)(data.ownerName, 'Owner name', 120),
        phone: (0, guards_1.requirePhone)(data.phone),
        address: (0, guards_1.optionalString)(data.address, 'Address', 300),
        updatedAt: firestore_1.FieldValue.serverTimestamp(),
    };
    await docRef.update(updates);
    await firebase_1.auth.updateUser(uid, { displayName: updates.storeName });
    // Password is optional on edit — only reset it when the admin typed a new one.
    if (data.password !== undefined && data.password !== null && data.password !== '') {
        await firebase_1.auth.updateUser(uid, { password: (0, guards_1.requirePassword)(data.password) });
        // Force existing app sessions to re-authenticate with the new password.
        await firebase_1.auth.revokeRefreshTokens(uid);
        firebase_functions_1.logger.info('Store owner password reset', { uid });
    }
    return { uid };
});
/**
 * Activate / deactivate a store. Disabling the Auth user is what actually locks
 * a store out: its refresh tokens are revoked, so the app is signed out on its
 * next token refresh rather than staying logged in until it happens to restart.
 */
exports.setStoreOwnerActive = (0, https_1.onCall)(async (request) => {
    (0, guards_1.requireAdmin)(request);
    const data = request.data ?? {};
    const uid = (0, guards_1.requireString)(data.uid, 'Store id', { max: 128 });
    if (typeof data.isActive !== 'boolean') {
        throw new https_1.HttpsError('invalid-argument', 'isActive must be true or false.');
    }
    const isActive = data.isActive;
    const docRef = firebase_1.db.collection(firebase_1.USERS).doc(uid);
    const snapshot = await docRef.get();
    if (!snapshot.exists || snapshot.get('role') !== 'store_owner') {
        throw new https_1.HttpsError('not-found', 'Store owner not found.');
    }
    await firebase_1.auth.updateUser(uid, { disabled: !isActive });
    if (!isActive) {
        await firebase_1.auth.revokeRefreshTokens(uid);
    }
    await docRef.update({
        isActive,
        // A deactivated store should stop receiving pushes immediately.
        ...(isActive ? {} : { fcmTokens: [] }),
        updatedAt: firestore_1.FieldValue.serverTimestamp(),
    });
    firebase_functions_1.logger.info('Store owner activation changed', { uid, isActive });
    return { uid, isActive };
});
//# sourceMappingURL=stores.js.map
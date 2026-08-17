/**
 * One-time bootstrap: create (or repair) the pharmacy owner's admin account.
 *
 * There is no self-registration anywhere in this system, so the very first
 * admin has to be made with the Admin SDK from a trusted machine.
 *
 * Usage:
 *   export GOOGLE_APPLICATION_CREDENTIALS=/path/to/serviceAccountKey.json
 *   export FIREBASE_PROJECT_ID=your-project-id
 *   node scripts/create-admin.mjs owner@example.com 'a-strong-password' 'Pharmacy Owner'
 *
 * Running it again for the same email resets that admin's password and
 * re-applies the admin claim — useful if the owner forgets the password.
 */
import { initializeApp, applicationDefault } from 'firebase-admin/app';
import { getAuth } from 'firebase-admin/auth';
import { getFirestore, FieldValue } from 'firebase-admin/firestore';

const [email, password, displayName = 'Pharmacy Admin'] = process.argv.slice(2);

if (!email || !password) {
  console.error(
    'Usage: node scripts/create-admin.mjs <email> <password> [display name]',
  );
  process.exit(1);
}

if (password.length < 8) {
  console.error('Choose an admin password of at least 8 characters.');
  process.exit(1);
}

initializeApp({
  credential: applicationDefault(),
  projectId: process.env.FIREBASE_PROJECT_ID,
});

const auth = getAuth();
const db = getFirestore();

let user;
try {
  user = await auth.getUserByEmail(email);
  await auth.updateUser(user.uid, { password, displayName, disabled: false });
  console.log(`Existing user ${email} updated.`);
} catch (error) {
  if (error.code !== 'auth/user-not-found') {
    throw error;
  }
  user = await auth.createUser({ email, password, displayName });
  console.log(`Created user ${email}.`);
}

await auth.setCustomUserClaims(user.uid, { role: 'admin' });

const now = FieldValue.serverTimestamp();
await db
  .collection('users')
  .doc(user.uid)
  .set(
    {
      role: 'admin',
      username: email.split('@')[0].toLowerCase(),
      storeName: null,
      ownerName: displayName,
      phone: null,
      address: null,
      isActive: true,
      fcmTokens: [],
      updatedAt: now,
      createdAt: now,
    },
    { merge: true },
  );

console.log(`Admin ready: ${email} (uid ${user.uid})`);
console.log('Sign in to the web dashboard with this email and password.');
process.exit(0);

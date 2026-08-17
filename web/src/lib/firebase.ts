import { initializeApp, type FirebaseApp } from 'firebase/app';
import { connectAuthEmulator, getAuth, type Auth } from 'firebase/auth';
import { connectFirestoreEmulator, getFirestore, type Firestore } from 'firebase/firestore';

export interface FirebaseWebConfig {
  apiKey: string;
  authDomain: string;
  projectId: string;
  storageBucket: string;
  messagingSenderId: string;
  appId: string;
}

// Assigned by initFirebase() before anything imports the app, so these are
// never read while still undefined. ES module live bindings keep importers in
// step with the assignment.
export let app: FirebaseApp;
export let auth: Auth;
export let db: Firestore;

export function initFirebase(config: FirebaseWebConfig): void {
  app = initializeApp(config);
  auth = getAuth(app);
  db = getFirestore(app);

  if (import.meta.env.VITE_USE_EMULATORS === 'true') {
    connectAuthEmulator(auth, 'http://127.0.0.1:9099', { disableWarnings: true });
    connectFirestoreEmulator(db, '127.0.0.1', 8080);
  }
}

/**
 * The config comes from the server at runtime (`/api/config`) rather than being
 * baked in at build time, so one build works against any project. Local dev
 * without the server running falls back to VITE_ variables.
 */
export async function loadFirebaseConfig(): Promise<FirebaseWebConfig> {
  const fromEnv = import.meta.env.VITE_FIREBASE_API_KEY;
  if (fromEnv) {
    return {
      apiKey: fromEnv,
      authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
      projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
      storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
      messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
      appId: import.meta.env.VITE_FIREBASE_APP_ID,
    };
  }

  const response = await fetch('/api/config');
  if (!response.ok) {
    throw new Error(
      'Could not load the Firebase configuration from the server. Is the pharmacy service running?',
    );
  }
  return (await response.json()) as FirebaseWebConfig;
}

export const USERS = 'users';
export const OFFERS = 'bonusOffers';
export const NOTIFICATIONS_LOG = 'notificationsLog';

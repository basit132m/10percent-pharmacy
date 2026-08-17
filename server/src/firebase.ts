import { cert, initializeApp } from 'firebase-admin/app';
import { getAuth } from 'firebase-admin/auth';
import { getFirestore } from 'firebase-admin/firestore';
import { getMessaging } from 'firebase-admin/messaging';

import type { AppConfig } from './config';

export const USERS = 'users';
export const OFFERS = 'bonusOffers';
export const NOTIFICATIONS_LOG = 'notificationsLog';

let initialised = false;

export function initFirebase(config: AppConfig): void {
  if (initialised) {
    return;
  }
  initializeApp({
    // The emulators authenticate nothing, so there is no key to load there.
    ...(config.serviceAccountPath
      ? { credential: cert(config.serviceAccountPath) }
      : {}),
    projectId: config.projectId,
  });
  initialised = true;
}

export const auth = () => getAuth();
export const db = () => getFirestore();
export const messaging = () => getMessaging();

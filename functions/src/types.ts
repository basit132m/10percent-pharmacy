import type { OfferStatus } from './status';

export type Role = 'admin' | 'store_owner';

/**
 * Store owners log in with a username, but Firebase Auth identifies users by
 * email. We keep one synthetic address per username on an internal domain that
 * receives no mail — store owners never see it, they only type the username.
 */
export const STORE_LOGIN_DOMAIN = 'stores.10percentpharmacy.local';

export const USERNAME_PATTERN = /^[a-z0-9][a-z0-9._-]{2,29}$/;

export function usernameToEmail(username: string): string {
  return `${username.trim().toLowerCase()}@${STORE_LOGIN_DOMAIN}`;
}

export interface UserDoc {
  role: Role;
  username: string;
  storeName: string | null;
  ownerName: string | null;
  phone: string | null;
  address: string | null;
  isActive: boolean;
  fcmTokens: string[];
  createdAt: FirebaseFirestore.Timestamp;
  updatedAt: FirebaseFirestore.Timestamp;
}

export interface OfferDoc {
  productName: string;
  buyQty: number;
  freeQty: number;
  /** 'YYYY-MM-DD' in Asia/Karachi. */
  startDate: string;
  /** 'YYYY-MM-DD' in Asia/Karachi. */
  expiryDate: string;
  status: OfferStatus;
  createdBy: string;
  notifiedAt: FirebaseFirestore.Timestamp | null;
  createdAt: FirebaseFirestore.Timestamp;
  updatedAt: FirebaseFirestore.Timestamp;
}

import { HttpsError, type CallableRequest } from 'firebase-functions/v2/https';

import { USERNAME_PATTERN } from './types';

/** Throws unless the caller is signed in as an admin. */
export function requireAdmin(request: CallableRequest): string {
  const auth = request.auth;
  if (!auth) {
    throw new HttpsError('unauthenticated', 'Sign in first.');
  }
  if (auth.token.role !== 'admin') {
    throw new HttpsError('permission-denied', 'Admin access required.');
  }
  return auth.uid;
}

export function requireString(
  value: unknown,
  field: string,
  { min = 1, max = 200 }: { min?: number; max?: number } = {},
): string {
  if (typeof value !== 'string') {
    throw new HttpsError('invalid-argument', `${field} must be text.`);
  }
  const trimmed = value.trim();
  if (trimmed.length < min || trimmed.length > max) {
    throw new HttpsError(
      'invalid-argument',
      `${field} must be between ${min} and ${max} characters.`,
    );
  }
  return trimmed;
}

/** Optional free-text field: returns null for empty/absent values. */
export function optionalString(
  value: unknown,
  field: string,
  max = 200,
): string | null {
  if (value === undefined || value === null || value === '') {
    return null;
  }
  return requireString(value, field, { min: 1, max });
}

export function requireUsername(value: unknown): string {
  const username = requireString(value, 'Username', { min: 3, max: 30 }).toLowerCase();
  if (!USERNAME_PATTERN.test(username)) {
    throw new HttpsError(
      'invalid-argument',
      'Username must be 3-30 characters: lowercase letters, digits, dot, dash or underscore, starting with a letter or digit.',
    );
  }
  return username;
}

export function requirePassword(value: unknown): string {
  if (typeof value !== 'string' || value.length < 6 || value.length > 128) {
    throw new HttpsError(
      'invalid-argument',
      'Password must be between 6 and 128 characters.',
    );
  }
  return value;
}

export function requirePhone(value: unknown): string | null {
  const phone = optionalString(value, 'Phone number', 20);
  if (phone !== null && !/^[+0-9][0-9 ()-]{6,19}$/.test(phone)) {
    throw new HttpsError('invalid-argument', 'Phone number looks invalid.');
  }
  return phone;
}

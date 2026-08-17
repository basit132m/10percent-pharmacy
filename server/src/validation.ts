/**
 * Request validation. Each helper throws an ApiError that the express error
 * handler turns into a 4xx with a message the dashboard shows as-is, so the
 * wording here is what the pharmacy owner reads.
 */

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

export const USERNAME_PATTERN = /^[a-z0-9][a-z0-9._-]{2,29}$/;

/**
 * Store owners log in with a username, but Firebase Auth identifies users by
 * email. Each username maps to a synthetic address on a domain that receives
 * no mail — store owners never see it.
 *
 * Must stay in step with STORE_LOGIN_DOMAIN in the Android app
 * (android/.../data/PharmacyRepository.kt).
 */
export const STORE_LOGIN_DOMAIN = 'stores.10percentpharmacy.local';

export function usernameToEmail(username: string): string {
  return `${username.trim().toLowerCase()}@${STORE_LOGIN_DOMAIN}`;
}

export function requireString(
  value: unknown,
  field: string,
  { min = 1, max = 200 }: { min?: number; max?: number } = {},
): string {
  if (typeof value !== 'string') {
    throw new ApiError(400, `${field} must be text.`);
  }
  const trimmed = value.trim();
  if (trimmed.length < min || trimmed.length > max) {
    throw new ApiError(
      400,
      `${field} must be between ${min} and ${max} characters.`,
    );
  }
  return trimmed;
}

/** Optional free-text field: returns null for empty or absent values. */
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
    throw new ApiError(
      400,
      'Username must be 3-30 characters: lowercase letters, digits, dot, dash or underscore, starting with a letter or digit.',
    );
  }
  return username;
}

export function requirePassword(value: unknown): string {
  if (typeof value !== 'string' || value.length < 6 || value.length > 128) {
    throw new ApiError(400, 'Password must be between 6 and 128 characters.');
  }
  return value;
}

export function requirePhone(value: unknown): string | null {
  const phone = optionalString(value, 'Phone number', 20);
  if (phone !== null && !/^[+0-9][0-9 ()-]{6,19}$/.test(phone)) {
    throw new ApiError(400, 'Phone number looks invalid.');
  }
  return phone;
}

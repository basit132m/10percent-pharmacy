/**
 * Calls to the pharmacy server, which runs on the same origin as this
 * dashboard. Every request carries the admin's Firebase ID token; the server
 * verifies it with the Admin SDK before touching an account.
 */
import { auth } from './firebase';

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const user = auth.currentUser;
  if (!user) {
    throw new Error('Sign in first.');
  }
  const token = await user.getIdToken();

  let response: Response;
  try {
    response = await fetch(path, {
      ...init,
      headers: {
        ...(init.body ? { 'content-type': 'application/json' } : {}),
        authorization: `Bearer ${token}`,
        ...init.headers,
      },
    });
  } catch {
    throw new Error('Could not reach the server. Check your connection.');
  }

  if (!response.ok) {
    // The server sends { error } for anything it rejects on purpose.
    const message = await response
      .json()
      .then((body: { error?: string }) => body.error)
      .catch(() => undefined);
    throw new Error(message ?? `Request failed (${response.status}).`);
  }

  return (await response.json()) as T;
}

export interface StoreOwnerInput {
  storeName: string;
  ownerName: string;
  phone: string;
  address: string;
  username?: string;
  password?: string;
}

export function createStoreOwner(input: StoreOwnerInput) {
  return request<{ uid: string; username: string }>('/api/stores', {
    method: 'POST',
    body: JSON.stringify(input),
  });
}

export function updateStoreOwner(uid: string, input: StoreOwnerInput) {
  return request<{ uid: string }>(`/api/stores/${encodeURIComponent(uid)}`, {
    method: 'PATCH',
    body: JSON.stringify(input),
  });
}

export function setStoreOwnerActive(uid: string, isActive: boolean) {
  return request<{ uid: string; isActive: boolean }>(
    `/api/stores/${encodeURIComponent(uid)}/active`,
    {
      method: 'POST',
      body: JSON.stringify({ isActive }),
    },
  );
}

export function refreshOfferStatuses() {
  return request<{ today: string; scanned: number; updated: number }>(
    '/api/offers/refresh-status',
    { method: 'POST' },
  );
}

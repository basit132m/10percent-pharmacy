/**
 * Admin authentication for the API.
 *
 * The dashboard signs in with the Firebase Auth JS SDK and sends the resulting
 * ID token as a bearer token. We verify it here with the Admin SDK, so the
 * server trusts Google's signature rather than anything the browser claims.
 */
import type { NextFunction, Request, Response } from 'express';

import { auth } from './firebase';
import { ApiError } from './validation';

export interface AdminRequest extends Request {
  adminUid?: string;
}

export async function requireAdmin(
  req: AdminRequest,
  _res: Response,
  next: NextFunction,
): Promise<void> {
  try {
    const header = req.header('authorization') ?? '';
    const [scheme, token] = header.split(' ');
    if (scheme?.toLowerCase() !== 'bearer' || !token) {
      throw new ApiError(401, 'Sign in first.');
    }

    // checkRevoked: a revoked session (deactivated admin) is rejected straight
    // away rather than staying valid until the token expires.
    const decoded = await auth().verifyIdToken(token, true);
    if (decoded.role !== 'admin') {
      throw new ApiError(403, 'Admin access required.');
    }

    req.adminUid = decoded.uid;
    next();
  } catch (error) {
    if (error instanceof ApiError) {
      next(error);
      return;
    }
    next(new ApiError(401, 'Your session has expired. Sign in again.'));
  }
}

"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.requireAdmin = requireAdmin;
exports.requireString = requireString;
exports.optionalString = optionalString;
exports.requireUsername = requireUsername;
exports.requirePassword = requirePassword;
exports.requirePhone = requirePhone;
const https_1 = require("firebase-functions/v2/https");
const types_1 = require("./types");
/** Throws unless the caller is signed in as an admin. */
function requireAdmin(request) {
    const auth = request.auth;
    if (!auth) {
        throw new https_1.HttpsError('unauthenticated', 'Sign in first.');
    }
    if (auth.token.role !== 'admin') {
        throw new https_1.HttpsError('permission-denied', 'Admin access required.');
    }
    return auth.uid;
}
function requireString(value, field, { min = 1, max = 200 } = {}) {
    if (typeof value !== 'string') {
        throw new https_1.HttpsError('invalid-argument', `${field} must be text.`);
    }
    const trimmed = value.trim();
    if (trimmed.length < min || trimmed.length > max) {
        throw new https_1.HttpsError('invalid-argument', `${field} must be between ${min} and ${max} characters.`);
    }
    return trimmed;
}
/** Optional free-text field: returns null for empty/absent values. */
function optionalString(value, field, max = 200) {
    if (value === undefined || value === null || value === '') {
        return null;
    }
    return requireString(value, field, { min: 1, max });
}
function requireUsername(value) {
    const username = requireString(value, 'Username', { min: 3, max: 30 }).toLowerCase();
    if (!types_1.USERNAME_PATTERN.test(username)) {
        throw new https_1.HttpsError('invalid-argument', 'Username must be 3-30 characters: lowercase letters, digits, dot, dash or underscore, starting with a letter or digit.');
    }
    return username;
}
function requirePassword(value) {
    if (typeof value !== 'string' || value.length < 6 || value.length > 128) {
        throw new https_1.HttpsError('invalid-argument', 'Password must be between 6 and 128 characters.');
    }
    return value;
}
function requirePhone(value) {
    const phone = optionalString(value, 'Phone number', 20);
    if (phone !== null && !/^[+0-9][0-9 ()-]{6,19}$/.test(phone)) {
        throw new https_1.HttpsError('invalid-argument', 'Phone number looks invalid.');
    }
    return phone;
}
//# sourceMappingURL=guards.js.map
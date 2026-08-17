"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.USERNAME_PATTERN = exports.STORE_LOGIN_DOMAIN = void 0;
exports.usernameToEmail = usernameToEmail;
/**
 * Store owners log in with a username, but Firebase Auth identifies users by
 * email. We keep one synthetic address per username on an internal domain that
 * receives no mail — store owners never see it, they only type the username.
 */
exports.STORE_LOGIN_DOMAIN = 'stores.10percentpharmacy.local';
exports.USERNAME_PATTERN = /^[a-z0-9][a-z0-9._-]{2,29}$/;
function usernameToEmail(username) {
    return `${username.trim().toLowerCase()}@${exports.STORE_LOGIN_DOMAIN}`;
}
//# sourceMappingURL=types.js.map
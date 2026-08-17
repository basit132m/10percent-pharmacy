"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.NOTIFICATIONS_LOG = exports.OFFERS = exports.USERS = exports.messaging = exports.auth = exports.db = void 0;
const app_1 = require("firebase-admin/app");
const auth_1 = require("firebase-admin/auth");
const firestore_1 = require("firebase-admin/firestore");
const messaging_1 = require("firebase-admin/messaging");
if ((0, app_1.getApps)().length === 0) {
    (0, app_1.initializeApp)();
}
exports.db = (0, firestore_1.getFirestore)();
exports.auth = (0, auth_1.getAuth)();
exports.messaging = (0, messaging_1.getMessaging)();
exports.USERS = 'users';
exports.OFFERS = 'bonusOffers';
exports.NOTIFICATIONS_LOG = 'notificationsLog';
//# sourceMappingURL=firebase.js.map
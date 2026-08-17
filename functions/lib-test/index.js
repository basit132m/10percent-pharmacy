"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.onOfferPublished = exports.syncOfferStatusOnEdit = exports.refreshOfferStatusesNow = exports.dailyOfferStatusCheck = exports.setStoreOwnerActive = exports.updateStoreOwner = exports.createStoreOwner = void 0;
/**
 * 10% Discount Pharmacy — bonus offer backend.
 *
 * Deployed region is asia-south1 (Mumbai), the closest to Kahror Pakka. The web
 * dashboard must call functions in the same region — see web/src/lib/firebase.ts.
 */
const v2_1 = require("firebase-functions/v2");
(0, v2_1.setGlobalOptions)({ region: 'asia-south1', maxInstances: 10 });
var stores_1 = require("./stores");
Object.defineProperty(exports, "createStoreOwner", { enumerable: true, get: function () { return stores_1.createStoreOwner; } });
Object.defineProperty(exports, "updateStoreOwner", { enumerable: true, get: function () { return stores_1.updateStoreOwner; } });
Object.defineProperty(exports, "setStoreOwnerActive", { enumerable: true, get: function () { return stores_1.setStoreOwnerActive; } });
var offers_1 = require("./offers");
Object.defineProperty(exports, "dailyOfferStatusCheck", { enumerable: true, get: function () { return offers_1.dailyOfferStatusCheck; } });
Object.defineProperty(exports, "refreshOfferStatusesNow", { enumerable: true, get: function () { return offers_1.refreshOfferStatusesNow; } });
Object.defineProperty(exports, "syncOfferStatusOnEdit", { enumerable: true, get: function () { return offers_1.syncOfferStatusOnEdit; } });
var notifications_1 = require("./notifications");
Object.defineProperty(exports, "onOfferPublished", { enumerable: true, get: function () { return notifications_1.onOfferPublished; } });
//# sourceMappingURL=index.js.map
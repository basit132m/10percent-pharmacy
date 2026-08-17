"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const node_test_1 = require("node:test");
const status_1 = require("./status");
(0, node_test_1.test)('active while more than three days remain', () => {
    strict_1.default.equal((0, status_1.computeOfferStatus)('2026-08-31', '2026-08-17'), 'active');
    strict_1.default.equal((0, status_1.computeOfferStatus)('2026-08-21', '2026-08-17'), 'active');
});
(0, node_test_1.test)('expiring soon inside the three day window, expiry day included', () => {
    strict_1.default.equal((0, status_1.computeOfferStatus)('2026-08-20', '2026-08-17'), 'expiring_soon');
    strict_1.default.equal((0, status_1.computeOfferStatus)('2026-08-18', '2026-08-17'), 'expiring_soon');
    strict_1.default.equal((0, status_1.computeOfferStatus)('2026-08-17', '2026-08-17'), 'expiring_soon');
});
(0, node_test_1.test)('expired only after the expiry date has passed', () => {
    strict_1.default.equal((0, status_1.computeOfferStatus)('2026-08-16', '2026-08-17'), 'expired');
    strict_1.default.equal((0, status_1.computeOfferStatus)('2025-01-01', '2026-08-17'), 'expired');
});
(0, node_test_1.test)('status transitions correctly across a month boundary', () => {
    strict_1.default.equal((0, status_1.computeOfferStatus)('2026-09-01', '2026-08-29'), 'expiring_soon');
    strict_1.default.equal((0, status_1.computeOfferStatus)('2026-09-01', '2026-08-28'), 'active');
    strict_1.default.equal((0, status_1.computeOfferStatus)('2026-09-01', '2026-09-02'), 'expired');
});
(0, node_test_1.test)('an offer starting in the future is still active', () => {
    // start 2026-09-10, expiry 2026-09-30, today 2026-08-17
    strict_1.default.equal((0, status_1.computeOfferStatus)('2026-09-30', '2026-08-17'), 'active');
});
(0, node_test_1.test)('daysBetween counts whole calendar days in both directions', () => {
    strict_1.default.equal((0, status_1.daysBetween)('2026-08-17', '2026-08-20'), 3);
    strict_1.default.equal((0, status_1.daysBetween)('2026-08-20', '2026-08-17'), -3);
    strict_1.default.equal((0, status_1.daysBetween)('2026-02-28', '2026-03-01'), 1);
    strict_1.default.equal((0, status_1.daysBetween)('2024-02-28', '2024-03-01'), 2); // leap year
});
(0, node_test_1.test)('daysBetween is unaffected by daylight-saving style offsets', () => {
    strict_1.default.equal((0, status_1.daysBetween)('2026-03-28', '2026-03-30'), 2);
    strict_1.default.equal((0, status_1.daysBetween)('2026-10-24', '2026-10-26'), 2);
});
(0, node_test_1.test)('isIsoDate rejects malformed and impossible dates', () => {
    strict_1.default.equal((0, status_1.isIsoDate)('2026-08-17'), true);
    strict_1.default.equal((0, status_1.isIsoDate)('2024-02-29'), true);
    strict_1.default.equal((0, status_1.isIsoDate)('2026-02-30'), false);
    strict_1.default.equal((0, status_1.isIsoDate)('2026-13-01'), false);
    strict_1.default.equal((0, status_1.isIsoDate)('17-08-2026'), false);
    strict_1.default.equal((0, status_1.isIsoDate)('2026-8-7'), false);
    strict_1.default.equal((0, status_1.isIsoDate)(''), false);
    strict_1.default.equal((0, status_1.isIsoDate)(20260817), false);
});
(0, node_test_1.test)('pharmacyToday returns the Asia/Karachi date, not the UTC one', () => {
    // 2026-08-17 20:30 UTC is already 2026-08-18 01:30 in Karachi (UTC+5).
    strict_1.default.equal((0, status_1.pharmacyToday)(new Date('2026-08-17T20:30:00Z')), '2026-08-18');
    strict_1.default.equal((0, status_1.pharmacyToday)(new Date('2026-08-17T18:00:00Z')), '2026-08-17');
});
//# sourceMappingURL=status.test.js.map
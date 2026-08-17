import assert from 'node:assert/strict';
import { test } from 'node:test';

import {
  computeOfferStatus,
  daysBetween,
  isIsoDate,
  pharmacyToday,
} from './status';

test('active while more than three days remain', () => {
  assert.equal(computeOfferStatus('2026-08-31', '2026-08-17'), 'active');
  assert.equal(computeOfferStatus('2026-08-21', '2026-08-17'), 'active');
});

test('expiring soon inside the three day window, expiry day included', () => {
  assert.equal(computeOfferStatus('2026-08-20', '2026-08-17'), 'expiring_soon');
  assert.equal(computeOfferStatus('2026-08-18', '2026-08-17'), 'expiring_soon');
  assert.equal(computeOfferStatus('2026-08-17', '2026-08-17'), 'expiring_soon');
});

test('expired only after the expiry date has passed', () => {
  assert.equal(computeOfferStatus('2026-08-16', '2026-08-17'), 'expired');
  assert.equal(computeOfferStatus('2025-01-01', '2026-08-17'), 'expired');
});

test('status transitions correctly across a month boundary', () => {
  assert.equal(computeOfferStatus('2026-09-01', '2026-08-29'), 'expiring_soon');
  assert.equal(computeOfferStatus('2026-09-01', '2026-08-28'), 'active');
  assert.equal(computeOfferStatus('2026-09-01', '2026-09-02'), 'expired');
});

test('an offer starting in the future is still active', () => {
  // start 2026-09-10, expiry 2026-09-30, today 2026-08-17
  assert.equal(computeOfferStatus('2026-09-30', '2026-08-17'), 'active');
});

test('daysBetween counts whole calendar days in both directions', () => {
  assert.equal(daysBetween('2026-08-17', '2026-08-20'), 3);
  assert.equal(daysBetween('2026-08-20', '2026-08-17'), -3);
  assert.equal(daysBetween('2026-02-28', '2026-03-01'), 1);
  assert.equal(daysBetween('2024-02-28', '2024-03-01'), 2); // leap year
});

test('daysBetween is unaffected by daylight-saving style offsets', () => {
  assert.equal(daysBetween('2026-03-28', '2026-03-30'), 2);
  assert.equal(daysBetween('2026-10-24', '2026-10-26'), 2);
});

test('isIsoDate rejects malformed and impossible dates', () => {
  assert.equal(isIsoDate('2026-08-17'), true);
  assert.equal(isIsoDate('2024-02-29'), true);
  assert.equal(isIsoDate('2026-02-30'), false);
  assert.equal(isIsoDate('2026-13-01'), false);
  assert.equal(isIsoDate('17-08-2026'), false);
  assert.equal(isIsoDate('2026-8-7'), false);
  assert.equal(isIsoDate(''), false);
  assert.equal(isIsoDate(20260817), false);
});

test('pharmacyToday returns the Asia/Karachi date, not the UTC one', () => {
  // 2026-08-17 20:30 UTC is already 2026-08-18 01:30 in Karachi (UTC+5).
  assert.equal(pharmacyToday(new Date('2026-08-17T20:30:00Z')), '2026-08-18');
  assert.equal(pharmacyToday(new Date('2026-08-17T18:00:00Z')), '2026-08-17');
});

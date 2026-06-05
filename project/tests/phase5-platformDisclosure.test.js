import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

// We import the constant and the localStorage helpers (not the React component itself).
import { PLATFORM_DISCLOSURE_TEXT, hasShownPlatformDisclosure, markPlatformDisclosureShown } from '../src/ui/components/PlatformDisclosure.js';

function stubLocalStorage(initial = {}) {
  globalThis.localStorage = {
    _data: { ...initial },
    getItem(k) { return Object.prototype.hasOwnProperty.call(this._data, k) ? this._data[k] : null; },
    setItem(k, v) { this._data[k] = String(v); },
    removeItem(k) { delete this._data[k]; },
  };
}
function unstubLocalStorage() { delete globalThis.localStorage; }

describe('5.2 Platform limitation disclosure', () => {
  test('PLATFORM_DISCLOSURE_TEXT matches the SPEC §7.2 exact string', () => {
    assert.equal(PLATFORM_DISCLOSURE_TEXT, 'Background reminders require notification permissions. Reliability when the app is closed depends on your device and browser.');
  });
  test('hasShownPlatformDisclosure returns false when localStorage flag not set', () => {
    stubLocalStorage();
    try { assert.equal(hasShownPlatformDisclosure(), false); } finally { unstubLocalStorage(); }
  });
  test('after markPlatformDisclosureShown, hasShownPlatformDisclosure returns true', () => {
    stubLocalStorage();
    try {
      markPlatformDisclosureShown();
      assert.equal(hasShownPlatformDisclosure(), true);
    } finally { unstubLocalStorage(); }
  });
  test('idempotent: calling markPlatformDisclosureShown twice does not throw and state remains true', () => {
    stubLocalStorage();
    try {
      markPlatformDisclosureShown();
      markPlatformDisclosureShown();
      assert.equal(hasShownPlatformDisclosure(), true);
    } finally { unstubLocalStorage(); }
  });
});

// Note: full DOM rendering tests of the React modal are skipped (no jsdom dep).
// The Phase 5 exit gate manual scenario verifies the rendered modal behavior in a real browser.
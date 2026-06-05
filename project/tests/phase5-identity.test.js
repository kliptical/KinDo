import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { resolveIdentity, setIdentity } from '../src/ui/identity.js';

// Simulate browser globals for the test scope.
// Helper: stub window.location and localStorage
function stubBrowser({ search = '', storage = {} } = {}) {
  globalThis.window = { location: { search, hash: '', href: 'http://test/' } };
  globalThis.localStorage = {
    _data: { ...storage },
    getItem(k) { return Object.prototype.hasOwnProperty.call(this._data, k) ? this._data[k] : null; },
    setItem(k, v) { this._data[k] = String(v); },
    removeItem(k) { delete this._data[k]; },
  };
}
function unstubBrowser() {
  delete globalThis.window;
  delete globalThis.localStorage;
}

describe('5.x identity resolution', () => {
  test('?as=parent:alice returns identity with role parent, userId urn:ftm:parent:alice', () => {
    stubBrowser({ search: '?as=parent:alice' });
    try {
      const id = resolveIdentity();
      assert.equal(id.role, 'parent');
      assert.equal(id.userId, 'urn:ftm:parent:alice');
    } finally { unstubBrowser(); }
  });

  test('?as=child:bob returns child identity', () => {
    stubBrowser({ search: '?as=child:bob' });
    try {
      const id = resolveIdentity();
      assert.equal(id.role, 'child');
      assert.equal(id.userId, 'urn:ftm:child:bob');
    } finally { unstubBrowser(); }
  });

  test('No URL param + no localStorage returns null', () => {
    stubBrowser({ search: '' });
    try {
      const id = resolveIdentity();
      assert.equal(id, null);
    } finally { unstubBrowser(); }
  });

  test('No URL param + valid localStorage JSON returns the stored identity', () => {
    const stored = { userId: 'urn:ftm:parent:carol', role: 'parent' };
    stubBrowser({ search: '', storage: { 'ftm.identity': JSON.stringify(stored) } });
    try {
      const id = resolveIdentity();
      assert.deepEqual(id, stored);
    } finally { unstubBrowser(); }
  });

  test('No URL param + invalid localStorage JSON returns null (does not throw)', () => {
    stubBrowser({ search: '', storage: { 'ftm.identity': '{not valid json' } });
    try {
      const id = resolveIdentity();
      assert.equal(id, null);
    } finally { unstubBrowser(); }
  });

  test('setIdentity persists to localStorage', () => {
    stubBrowser({ search: '' });
    try {
      const identity = { userId: 'urn:ftm:child:dave', role: 'child' };
      setIdentity(identity);
      const raw = globalThis.localStorage.getItem('ftm.identity');
      assert.deepEqual(JSON.parse(raw), identity);
    } finally { unstubBrowser(); }
  });
});

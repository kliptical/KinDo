import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { parseRoute } from '../src/ui/router.js';

describe('5.3 router parseRoute', () => {
  test('# or empty hash returns home view', () => {
    assert.deepEqual(parseRoute(''),    { view: 'home', params: {} });
    assert.deepEqual(parseRoute('#'),   { view: 'home', params: {} });
    assert.deepEqual(parseRoute('#/'),  { view: 'home', params: {} });
    assert.deepEqual(parseRoute(null),  { view: 'home', params: {} });
  });

  test('#/parent/dashboard returns view parent-dashboard', () => {
    assert.deepEqual(parseRoute('#/parent/dashboard'), { view: 'parent-dashboard', params: {} });
  });

  test('#/parent/create returns view parent-create', () => {
    assert.deepEqual(parseRoute('#/parent/create'), { view: 'parent-create', params: {} });
  });

  test('#/parent/instance/abc returns view parent-instance params.id === abc', () => {
    const result = parseRoute('#/parent/instance/abc');
    assert.equal(result.view, 'parent-instance');
    assert.equal(result.params.id, 'abc');
  });

  test('#/child/tasks returns view child-tasks', () => {
    assert.deepEqual(parseRoute('#/child/tasks'), { view: 'child-tasks', params: {} });
  });

  test('#/child/instance/xyz returns view child-instance params.id === xyz', () => {
    const result = parseRoute('#/child/instance/xyz');
    assert.equal(result.view, 'child-instance');
    assert.equal(result.params.id, 'xyz');
  });

  test('#/instance/deep-id returns view instance (role-agnostic)', () => {
    const result = parseRoute('#/instance/deep-id');
    assert.equal(result.view, 'instance');
    assert.equal(result.params.id, 'deep-id');
  });

  test('#/unknown returns view not-found', () => {
    assert.deepEqual(parseRoute('#/unknown'), { view: 'not-found', params: {} });
  });

  test('leading slash before hash is normalized: /#/parent/dashboard parses same as #/parent/dashboard', () => {
    assert.deepEqual(
      parseRoute('/#/parent/dashboard'),
      parseRoute('#/parent/dashboard'),
    );
  });
});

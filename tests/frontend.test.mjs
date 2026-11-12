import test from 'node:test';
import assert from 'node:assert/strict';
import { splitLines, validateLines, badgeClass } from '../sensitive_detector/web/app.js';

test('TXT import preserves HTML as text and handles CRLF', () => {
  assert.deepEqual(splitLines('  第一条\r\n\n<img src=x>\n'), ['第一条', '<img src=x>']);
});
test('batch limits and Unicode character counts match Python', () => {
  assert.throws(() => validateLines([]));
  assert.throws(() => validateLines(Array(101).fill('a')));
  assert.throws(() => validateLines(['a'.repeat(8001)]));
  assert.throws(() => validateLines(Array(5).fill('a'.repeat(8000))));
  assert.equal(validateLines(['😀'.repeat(8000)]).length, 1);
});
test('review and quote badges have distinct styles', () => {
  assert.equal(badgeClass(1), 'warn');
  assert.equal(badgeClass(2), 'quote');
  assert.equal(badgeClass(0), 'neutral');
});

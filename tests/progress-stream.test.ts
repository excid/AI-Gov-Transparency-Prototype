import assert from 'node:assert/strict';
import test from 'node:test';

import { decodeProgressLines } from '../lib/progress-stream.ts';

test('decodes split NDJSON progress and result events without losing bytes', () => {
  const decoder = decodeProgressLines();
  assert.deepEqual(decoder.push('{"type":"progress","stage":"ocr","percent":15}\n{"type":"pro'), [
    { type: 'progress', stage: 'ocr', percent: 15 },
  ]);
  assert.deepEqual(decoder.push('gress","stage":"llm","percent":75}\n'), [
    { type: 'progress', stage: 'llm', percent: 75 },
  ]);
  assert.deepEqual(decoder.finish(), []);
});

test('rejects malformed progress lines instead of silently hanging', () => {
  const decoder = decodeProgressLines();
  assert.throws(() => decoder.push('not-json\n'), /Invalid progress stream/);
});

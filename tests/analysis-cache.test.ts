import assert from 'node:assert/strict';
import test from 'node:test';

import { analysisCacheKey, getCachedAnalysis, putCachedAnalysis } from '../lib/analysis-cache.ts';

class MemoryStore {
  values = new Map<string, unknown>();
  async get(key: string) { return this.values.get(key); }
  async put(key: string, value: unknown) { this.values.set(key, value); }
}

test('same bytes and pipeline version produce the same cache key', async () => {
  const first = await analysisCacheKey(new Uint8Array([1, 2, 3]), 'vision-v1');
  const second = await analysisCacheKey(new Uint8Array([1, 2, 3]), 'vision-v1');
  const changed = await analysisCacheKey(new Uint8Array([1, 2, 3]), 'vision-v2');

  assert.equal(first, second);
  assert.notEqual(first, changed);
});

test('cached analysis is returned only for the matching versioned PDF key', async () => {
  const store = new MemoryStore();
  const bytes = new Uint8Array([9, 8, 7]);
  const result = { summary: 'cached result' };

  await putCachedAnalysis(store, bytes, 'vision-v1', result);

  assert.deepEqual(await getCachedAnalysis(store, bytes, 'vision-v1'), result);
  assert.equal(await getCachedAnalysis(store, bytes, 'vision-v2'), undefined);
});

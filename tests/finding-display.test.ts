import assert from 'node:assert/strict';
import test from 'node:test';

import { findingPresentation } from '../lib/finding-display.ts';

test('presents an LLM finding as an AI summary with page reference', () => {
  assert.deepEqual(findingPresentation({ source: 'llm', page: 2, confidence: 0.834 }), {
    sourceLabel: 'สรุปโดย AI',
    pageLabel: 'TOR หน้า 2',
    confidenceLabel: 'ความมั่นใจ 83%',
    lowConfidence: false,
  });
});

test('warns when source evidence has low confidence', () => {
  const presentation = findingPresentation({ source: 'rule', page: 7, confidence: 0.49 });

  assert.equal(presentation.sourceLabel, 'กฎตรวจสอบ');
  assert.equal(presentation.lowConfidence, true);
});

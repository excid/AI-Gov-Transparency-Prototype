import assert from 'node:assert/strict';
import test from 'node:test';

import { projectTitle } from '../lib/project-display.ts';

test('uses the procurement project name instead of its department', () => {
  assert.equal(
    projectTitle({ project_name: 'จ้างก่อสร้างอาคารศูนย์บริการ', project_id: 'P-001' }),
    'จ้างก่อสร้างอาคารศูนย์บริการ',
  );
});

test('does not invent a project name when source data omitted it', () => {
  assert.equal(projectTitle({ project_name: null, project_id: 'P-001' }), 'ไม่พบชื่อโครงการในชุดข้อมูล');
});

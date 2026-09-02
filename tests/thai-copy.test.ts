import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const websiteCopy = [
  'app/page.tsx',
  'app/layout.tsx',
  'app/api/analyze-tor/route.ts',
  'lib/finding-display.ts',
].map((path) => readFileSync(path, 'utf8')).join('\n');

test('website avoids promotional and translated-sounding Thai copy', () => {
  for (const phrase of [
    'เห็นสัญญาณเสี่ยง',
    'ก่อนความเสียหายเกิดขึ้น',
    'ผลลัพธ์ที่ตรวจย้อนกลับได้',
    'หนึ่งเอกสาร สามชั้นการตรวจสอบ',
    'ML งดให้คะแนน',
    'ผลลัพธ์เป็นสัญญาณ',
  ]) {
    assert.equal(websiteCopy.includes(phrase), false, `remove: ${phrase}`);
  }
});

test('website uses concise procurement-review language', () => {
  for (const phrase of [
    'ตรวจ TOR ก่อนตัดสินใจ',
    'ประเด็นที่ควรตรวจต่อ',
    'ผู้ตรวจต้องยืนยันจากเอกสารต้นฉบับ',
  ]) {
    assert.equal(websiteCopy.includes(phrase), true, `missing: ${phrase}`);
  }
});

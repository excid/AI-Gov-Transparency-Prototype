import unittest

from ai_gov_transparency.ocr import PageText
from ai_gov_transparency.tor_rules import evaluate_rules, normalize_thai_digits


class TorRuleTests(unittest.TestCase):
    def test_preserves_full_rule_paragraph_beyond_old_260_character_limit(self):
        paragraph = (
            "รายละเอียดประกอบ " * 20
            + " อาคารสูงไม่น้อยกว่า 20 ชั้น ขนาด 30 เมตร ความจุอย่างน้อย 500 หน่วย "
            + "ข้อความท้ายข้อกำหนดที่ต้องแสดงครบ"
        )
        finding = evaluate_rules([PageText(8, paragraph, False, 1.0)])[0]

        self.assertGreater(len(finding.evidence), 260)
        self.assertIn("ข้อความท้ายข้อกำหนดที่ต้องแสดงครบ", finding.evidence)

    def test_normalizes_thai_digits(self):
        self.assertEqual(normalize_thai_digits("๕๐๐,๐๐๐ บาท ๒๕ ปี"), "500,000 บาท 25 ปี")

    def test_detects_all_six_rule_families_with_page_evidence(self):
        pages = [
            PageText(1, "วงเงินงบประมาณ 525,000,000 บาท ผู้ยื่นต้องมีผลงานไม่น้อยกว่า 500,000,000 บาท ซึ่งเป็นสัญญาเดียวกัน", False, 1.0),
            PageText(2, "ต้องใช้เครื่องปรับอากาศยี่ห้อ ACME รุ่น X1 เท่านั้น ห้ามใช้เทียบเท่า และต้องมีใบรับรอง ISO 99999", False, 1.0),
            PageText(3, "อาคารสูงไม่น้อยกว่า 20 ชั้น มีชั้นใต้ดิน 1 ชั้น ระบบ Post-Tension และลิฟต์ดับเพลิง", False, 1.0),
            PageText(4, "ผู้อำนวยการโครงการต้องมีประสบการณ์ไม่น้อยกว่า 25 ปี และผ่านงานอย่างน้อย 5 โครงการ", False, 1.0),
        ]
        findings = evaluate_rules(pages)
        categories = {finding.category for finding in findings}
        self.assertEqual(categories, {
            "previous_work_percentage", "brand_specific", "unnecessary_certificate",
            "narrow_technical_requirement", "experience_or_personnel", "other_lock_spec",
        })
        previous = next(item for item in findings if item.category == "previous_work_percentage")
        self.assertEqual(previous.page, 1)
        self.assertGreater(previous.details["ratio_percent"], 95)
        self.assertIn("500,000,000", previous.evidence)


if __name__ == "__main__":
    unittest.main()

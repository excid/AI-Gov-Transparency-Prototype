import math
import unittest

from ai_gov_transparency.ocr import PageText
from ai_gov_transparency.tor_features import extract_preaward_features


class TorFeatureTests(unittest.TestCase):
    def test_extracts_current_project_display_information(self):
        pages = [PageText(1, "ชื่อโครงการ จ้างก่อสร้างอาคารศูนย์บริการ\nวงเงินงบประมาณ 10,000,000 บาท ราคากลาง 9,500,000 บาท ระยะเวลาดำเนินการ 180 วัน วิธีประกวดราคาอิเล็กทรอนิกส์ ปีงบประมาณ พ.ศ. 2568", False, 1.0)]

        result = extract_preaward_features(pages).as_project_summary()

        self.assertEqual(result["project_name"], "จ้างก่อสร้างอาคารศูนย์บริการ")
        self.assertEqual(result["budget_baht"], 10_000_000)
        self.assertEqual(result["reference_price_baht"], 9_500_000)
        self.assertEqual(result["duration_days"], 180)
        self.assertEqual(result["fiscal_year"], 2568)

    def test_extracts_only_preaward_features(self):
        pages = [PageText(1, "วงเงินงบประมาณ 10,000,000 บาท ราคากลาง 9,500,000 บาท ระยะเวลาดำเนินการ 180 วัน วิธีประกวดราคาอิเล็กทรอนิกส์", False, 1.0)]
        result = extract_preaward_features(pages)
        self.assertAlmostEqual(result.log_budget, math.log1p(10_000_000))
        self.assertEqual(result.reference_to_budget_ratio, 0.95)
        self.assertAlmostEqual(result.log_duration_days, math.log1p(180))
        self.assertEqual(result.missing_core_field_count, 0)
        self.assertNotIn("agreed_price", result.as_model_row())


if __name__ == "__main__":
    unittest.main()

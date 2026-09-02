import math
import unittest

from ai_gov_transparency.ocr import PageText
from ai_gov_transparency.tor_features import extract_preaward_features


class TorFeatureTests(unittest.TestCase):
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

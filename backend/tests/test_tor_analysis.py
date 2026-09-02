import unittest
from unittest.mock import patch

from ai_gov_transparency.ocr import PageText
from ai_gov_transparency.tor_analysis import analyze_pages
from ai_gov_transparency.tor_llm import LlmResult
from ai_gov_transparency.ocr import PageText
from ai_gov_transparency.tor_analysis import analyze_tor
from ai_gov_transparency.tor_rules import Finding


class TorAnalysisTests(unittest.TestCase):
    def test_returns_current_project_before_ui_risk_rendering(self):
        pages = [PageText(1, "ชื่อโครงการ จ้างก่อสร้างอาคารศูนย์บริการ\nวงเงินงบประมาณ 10,000,000 บาท ราคากลาง 9,500,000 บาท ระยะเวลาดำเนินการ 180 วัน วิธีประกวดราคาอิเล็กทรอนิกส์", False, 1.0)]

        result = analyze_pages(pages, llm_result=None, model_artifact=None)

        self.assertEqual(result["current_project"]["project_name"], "จ้างก่อสร้างอาคารศูนย์บริการ")
        self.assertEqual(result["current_project"]["budget_baht"], 10_000_000)

    def test_analyze_tor_reports_real_pipeline_stages_in_order(self):
        events = []
        pages = [PageText(page_number=1, text="ข้อกำหนด", ocr_used=True, quality=0.9)]
        with (
            patch("ai_gov_transparency.tor_analysis.extract_pdf_pages", return_value=pages),
            patch("ai_gov_transparency.tor_analysis.analyze_with_llm", return_value=None),
            patch("ai_gov_transparency.tor_analysis.load_model_artifact", return_value=None),
        ):
            analyze_tor(b"%PDF-test", on_progress=lambda stage, percent: events.append((stage, percent)))

        self.assertEqual(events, [("ocr", 15), ("llm", 60), ("screening", 90), ("complete", 100)])

    def test_analyze_tor_uses_filename_when_pdf_has_no_project_name(self):
        pages = [PageText(page_number=1, text="วงเงินงบประมาณ 1,000,000 บาท ราคากลาง 950,000 บาท ระยะเวลา 60 วัน วิธีประกวดราคาอิเล็กทรอนิกส์", ocr_used=False, quality=1.0)]
        with (
            patch("ai_gov_transparency.tor_analysis.extract_pdf_pages", return_value=pages),
            patch("ai_gov_transparency.tor_analysis.analyze_with_llm", return_value=None),
            patch("ai_gov_transparency.tor_analysis.load_model_artifact", return_value=None),
        ):
            result = analyze_tor(b"%PDF-test", filename="โครงการก่อสร้างศูนย์บริการ.pdf")

        self.assertEqual(result["current_project"]["project_name"], "โครงการก่อสร้างศูนย์บริการ")

    def test_llm_project_name_is_used_before_filename_and_for_similarity(self):
        pages = [PageText(page_number=1, text="วงเงินงบประมาณ 1,000,000 บาท ราคากลาง 950,000 บาท ระยะเวลา 60 วัน วิธีประกวดราคาอิเล็กทรอนิกส์", ocr_used=False, quality=1.0)]
        llm = LlmResult("สรุป", (), project_name="จ้างก่อสร้างอาคารศูนย์บริการ")

        result = analyze_pages(pages, llm_result=llm, model_artifact=None)

        self.assertEqual(result["current_project"]["project_name"], "จ้างก่อสร้างอาคารศูนย์บริการ")
        self.assertEqual(result["features"]["project_name"], "จ้างก่อสร้างอาคารศูนย์บริการ")

    def test_returns_rules_when_llm_and_model_are_unavailable(self):
        pages = [PageText(1, "วงเงินงบประมาณ 100,000,000 บาท ต้องมีผลงานไม่น้อยกว่า 90,000,000 บาท", False, 1.0)]
        result = analyze_pages(pages, llm_result=None, model_artifact=None)
        self.assertEqual(result["status"], "completed_with_warnings")
        self.assertEqual(result["findings"][0]["source"], "rule")
        self.assertTrue(result["model"]["abstained"])
        self.assertEqual(result["model"]["similar_projects"], ())
        self.assertIn("LLM", " ".join(result["warnings"]))

    def test_does_not_double_count_same_category_and_page(self):
        pages = [PageText(1, "วงเงินงบประมาณ 100,000,000 บาท ต้องมีผลงานไม่น้อยกว่า 90,000,000 บาท", False, 1.0)]
        llm = LlmResult("สรุป", (Finding("previous_work_percentage", "high", "llm", "ต้องมีผลงานไม่น้อยกว่า 90,000,000 บาท", 1, "สูง", 0.9),))
        result = analyze_pages(pages, llm_result=llm, model_artifact=None)
        matching = [row for row in result["findings"] if row["category"] == "previous_work_percentage"]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0]["source"], "rule")


if __name__ == "__main__":
    unittest.main()

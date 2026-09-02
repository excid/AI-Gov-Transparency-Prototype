import tempfile
import unittest
from pathlib import Path

import pandas as pd

from ai_gov_transparency.tor_features import PreAwardFeatures
from ai_gov_transparency.tor_model import fit_preaward_model, load_preaward_artifact, save_preaward_artifact, score_preaward


class TorModelTests(unittest.TestCase):
    def test_abstains_when_fewer_than_two_numeric_features_exist(self):
        result = score_preaward(PreAwardFeatures(log_budget=12.0), None)
        self.assertTrue(result.abstained)
        self.assertIn("อย่างน้อย 2", result.reason)

    def test_fits_and_scores_with_reproducible_contract(self):
        frame = pd.DataFrame([
            {"project_id": f"P{i}", "project_money_baht": 1_000_000 + i * 20_000, "reference_price_baht": 950_000 + i * 20_000, "mean_contract_duration_days": 90 + i, "project_type_name": "งานก่อสร้าง", "purchase_method_name": "e-bidding", "fiscal_year": 2568}
            for i in range(40)
        ])
        artifact = fit_preaward_model(frame, max_rows=40, random_state=42)
        features = PreAwardFeatures(log_budget=18.0, reference_to_budget_ratio=0.95, log_duration_days=5.0, missing_core_field_count=0, project_type_name="งานก่อสร้าง", purchase_method_name="e-bidding")
        result = score_preaward(features, artifact)
        self.assertFalse(result.abstained)
        self.assertGreaterEqual(result.percentile, 0)
        self.assertLessEqual(result.percentile, 100)
        self.assertEqual(result.model_version, "tor-isolation-forest-0.1")
        self.assertGreaterEqual(result.cohort_size, 30)

    def test_saves_and_loads_versioned_artifact(self):
        frame = pd.DataFrame([{"project_id": f"P{i}", "project_money_baht": i + 1, "reference_price_baht": i + 1, "mean_contract_duration_days": 30} for i in range(30)])
        with tempfile.TemporaryDirectory() as directory:
            path = save_preaward_artifact(fit_preaward_model(frame, max_rows=30), Path(directory) / "model.joblib")
            self.assertEqual(load_preaward_artifact(path).model_version, "tor-isolation-forest-0.1")

    def test_returns_three_nearest_projects_with_display_metadata(self):
        frame = pd.DataFrame([
            {
                "project_id": f"P{i}",
                "project_name": f"โครงการก่อสร้าง {i}",
                "project_money_baht": 1_000_000 + i * 100_000,
                "reference_price_baht": 950_000 + i * 95_000,
                "mean_contract_duration_days": 100 + i,
                "project_type_name": "งานก่อสร้าง",
                "purchase_method_name": "e-bidding",
                "dept_name": f"หน่วยงาน {i}",
                "fiscal_year": 2568,
            }
            for i in range(40)
        ])
        artifact = fit_preaward_model(frame, max_rows=40, random_state=42)
        features = PreAwardFeatures(
            log_budget=__import__("math").log1p(2_000_000),
            reference_to_budget_ratio=0.95,
            log_duration_days=__import__("math").log1p(110),
            missing_core_field_count=0,
            project_type_name="งานก่อสร้าง",
            purchase_method_name="e-bidding",
        )

        result = score_preaward(features, artifact)

        self.assertEqual(len(result.similar_projects), 3)
        self.assertEqual(result.similar_projects[0].project_id, "P10")
        self.assertEqual(result.similar_projects[0].project_name, "โครงการก่อสร้าง 10")
        self.assertEqual(result.similar_projects[0].department, "หน่วยงาน 10")
        self.assertGreaterEqual(result.similar_projects[0].similarity_percent, result.similar_projects[1].similarity_percent)

    def test_project_name_similarity_can_outrank_a_slightly_closer_budget(self):
        frame = pd.DataFrame([
            {
                "project_id": f"P{i}",
                "project_name": "จ้างบำรุงรักษาระบบไฟฟ้า" if i == 11 else f"จัดซื้อวัสดุสำนักงาน {i}",
                "project_money_baht": 1_000_000 + i * 100_000,
                "reference_price_baht": 950_000 + i * 95_000,
                "mean_contract_duration_days": 100 + i,
                "project_type_name": "งานก่อสร้าง",
                "purchase_method_name": "e-bidding",
                "dept_name": f"หน่วยงาน {i}",
                "fiscal_year": 2568,
            }
            for i in range(40)
        ])
        artifact = fit_preaward_model(frame, max_rows=40, random_state=42)
        features = PreAwardFeatures(
            log_budget=__import__("math").log1p(2_000_000),
            reference_to_budget_ratio=0.95,
            log_duration_days=__import__("math").log1p(110),
            missing_core_field_count=0,
            project_type_name="งานก่อสร้าง",
            purchase_method_name="e-bidding",
            project_name="จ้างบำรุงรักษาระบบไฟฟ้า",
        )

        result = score_preaward(features, artifact)

        self.assertEqual(result.similar_projects[0].project_id, "P11")



if __name__ == "__main__":
    unittest.main()

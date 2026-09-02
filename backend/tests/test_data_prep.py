import json
import tempfile
import unittest
from pathlib import Path

from ai_gov_transparency.data_prep import prepare_training_frame, write_training_csv


class DataPreparationTests(unittest.TestCase):
    def test_prepares_features_and_optional_sidecars(self):
        project_payload = {
            "data": [
                {
                    "project_id": "P-001",
                    "year": 2568,
                    "project_money": 1000000,
                    "price_build": 950000,
                    "sum_price_agree": 900000,
                    "project_type_name": "จ้างก่อสร้าง",
                    "purchase_method_name": "e-bidding",
                    "dept_name": "กรมทดสอบ",
                    "province": "กรุงเทพมหานคร",
                    "project_location": {"lat": 13.7, "lon": 100.5},
                    "geom": "POINT(100.5 13.7)",
                    "contract": [
                        {
                            "winner_name": "บริษัท ก",
                            "contract_date": "1 ม.ค. 68",
                            "contract_finish_date": "1 ก.ค. 68",
                        }
                    ],
                },
                {"project_money": 10},
            ]
        }
        bid_payload = {
            "data": [
                {
                    "project_id": "P-001",
                    "bidder": [
                        {"merchant_name": "บริษัท ก", "submit_price": 900000},
                        {"merchant_name": "บริษัท ข", "submit_price": 930000},
                    ],
                }
            ]
        }
        cost_payload = {
            "data": [
                {
                    "project_id": "P-001",
                    "installment": [
                        {"percent_working": "80", "percent_withdraw": 70},
                        {"percent_working": "100", "percent_withdraw": 90},
                    ],
                }
            ]
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            projects = temp_path / "projects.json"
            bids = temp_path / "bids.json"
            cost = temp_path / "cost.json"
            labels = temp_path / "labels.csv"
            projects.write_text(json.dumps(project_payload), encoding="utf-8")
            bids.write_text(json.dumps(bid_payload), encoding="utf-8")
            cost.write_text(json.dumps(cost_payload), encoding="utf-8")
            labels.write_text("project_id,outcome_label\nP-001,confirmed_issue\n", encoding="utf-8")
            frame = prepare_training_frame([projects], [bids], [cost], labels)
            output = write_training_csv(frame, temp_path / "training.csv")
            exported = output.read_text(encoding="utf-8-sig")

        self.assertEqual(len(frame), 1)
        row = frame.iloc[0]
        self.assertEqual(row["project_id"], "P-001")
        self.assertAlmostEqual(row["discount_from_reference_ratio"], 50000 / 950000)
        self.assertEqual(row["bidder_count"], 2)
        self.assertAlmostEqual(row["bid_price_spread_ratio"], 30000 / 900000)
        self.assertEqual(row["has_cost_record"], 1)
        self.assertEqual(row["cost_progress_withdraw_gap"], 10)
        self.assertEqual(row["outcome_label"], "confirmed_issue")
        self.assertNotIn("winner_tin", frame.columns)
        self.assertIn("cost_progress_withdraw_gap", exported)


if __name__ == "__main__":
    unittest.main()

import unittest
import json
from unittest.mock import patch

from fastapi.testclient import TestClient

from ai_gov_transparency.service import app, cors_origins


class ScoringServiceTests(unittest.TestCase):
    def test_parses_deployed_site_origins_from_environment_value(self):
        self.assertEqual(
            cors_origins("https://example.chatgpt.site, http://localhost:3000 "),
            ["https://example.chatgpt.site", "http://localhost:3000"],
        )

    def test_streams_progress_before_final_analysis(self):
        def analyze(_payload, *, filename, on_progress):
            self.assertEqual(filename, "tor.pdf")
            on_progress("ocr", 15)
            on_progress("complete", 100)
            return {"summary": "done"}

        with patch("ai_gov_transparency.service.analyze_tor", side_effect=analyze):
            response = TestClient(app).post(
                "/analyze-tor/stream",
                files={"file": ("tor.pdf", b"%PDF-test", "application/pdf")},
            )

        self.assertEqual(response.status_code, 200)
        events = [json.loads(line) for line in response.text.splitlines()]
        self.assertEqual(events[0], {"type": "progress", "stage": "received", "percent": 5})
        self.assertEqual(events[1], {"type": "progress", "stage": "ocr", "percent": 15})
        self.assertEqual(events[-1], {"type": "result", "data": {"summary": "done"}})
    def test_rejects_non_pdf_tor_upload(self):
        response = TestClient(app).post("/analyze-tor", files={"file": ("tor.txt", b"not a pdf", "text/plain")})
        self.assertEqual(response.status_code, 415)

    def test_scores_official_project_records_as_one_peer_cohort(self):
        projects = [
            {
                "project_id": "P-001",
                "year": 2568,
                "project_money": 1_000_000,
                "price_build": 950_000,
                "sum_price_agree": 900_000,
                "dept_name": "กรม ก",
                "province": "กรุงเทพมหานคร",
            },
            {
                "project_id": "P-002",
                "year": 2568,
                "project_money": 1_050_000,
                "price_build": 980_000,
                "sum_price_agree": 920_000,
                "dept_name": "กรม ก",
                "province": "กรุงเทพมหานคร",
            },
            {
                "project_id": "P-003",
                "year": 2568,
                "project_money": 50_000_000,
                "price_build": 49_500_000,
                "sum_price_agree": 49_490_000,
                "dept_name": "กรม ข",
                "province": "เชียงใหม่",
            },
        ]

        response = TestClient(app).post("/score", json={"projects": projects})

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["cohortSize"], 3)
        self.assertEqual(body["modelVersion"], "isolation-forest-0.1")
        self.assertEqual({score["projectId"] for score in body["scores"]}, {"P-001", "P-002", "P-003"})
        self.assertTrue(all(0 < score["percentile"] <= 100 for score in body["scores"]))
        self.assertTrue(all("priceDifferencePercent" in score["factors"] for score in body["scores"]))

    def test_rejects_cohorts_too_small_for_scoring(self):
        response = TestClient(app).post(
            "/score",
            json={"projects": [{"project_id": "P-001", "year": 2568, "project_money": 100}]},
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"], "ต้องมีโครงการอย่างน้อย 3 รายการเพื่อเปรียบเทียบ")


if __name__ == "__main__":
    unittest.main()

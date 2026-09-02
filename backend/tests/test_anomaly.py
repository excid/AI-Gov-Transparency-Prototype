import unittest
import warnings

import pandas as pd

from ai_gov_transparency.anomaly import score_anomalies
from ai_gov_transparency.data_prep import prepare_training_records


class AnomalyTests(unittest.TestCase):
    def test_returns_peer_relative_percentiles(self):
        frame = pd.DataFrame(
            [
                {"project_id": "A", "fiscal_year": 2568, "project_money_baht": 10, "agreed_price_baht": 9, "dept_name": "X"},
                {"project_id": "B", "fiscal_year": 2568, "project_money_baht": 11, "agreed_price_baht": 10, "dept_name": "X"},
                {"project_id": "C", "fiscal_year": 2568, "project_money_baht": 1000, "agreed_price_baht": 999, "dept_name": "X"},
            ]
        )
        results = score_anomalies(frame)
        self.assertEqual(len(results), 3)
        self.assertTrue(all(0 < result.percentile <= 100 for result in results))
        self.assertEqual({result.model_version for result in results}, {"isolation-forest-0.1"})

    def test_ignores_features_that_are_missing_for_the_entire_cohort(self):
        frame = prepare_training_records(
            [
                {"project_id": "A", "year": 2568, "project_money": 10, "sum_price_agree": 9},
                {"project_id": "B", "year": 2568, "project_money": 11, "sum_price_agree": 10},
                {"project_id": "C", "year": 2568, "project_money": 1000, "sum_price_agree": 999},
            ]
        )

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            score_anomalies(frame)

        self.assertEqual(caught, [])


if __name__ == "__main__":
    unittest.main()

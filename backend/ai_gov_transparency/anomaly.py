"""Offline anomaly scoring for procurement features.

Scores are peer-relative percentiles, never corruption probabilities.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import IsolationForest
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, RobustScaler

from .data_prep import CATEGORY_COLUMNS, FEATURE_COLUMNS, IDENTIFIER_COLUMNS


@dataclass(frozen=True)
class ScoringResult:
    project_id: str
    fiscal_year: int | None
    raw_score: float
    percentile: float
    model_version: str = "isolation-forest-0.1"


def score_anomalies(frame: pd.DataFrame, random_state: int = 42) -> list[ScoringResult]:
    """Fit within supplied peer cohort and return high-is-unusual percentiles."""
    if len(frame) < 3:
        raise ValueError("At least three comparable projects are required for anomaly scoring")
    numeric = [column for column in FEATURE_COLUMNS if column in frame and frame[column].notna().any()]
    categories = [column for column in CATEGORY_COLUMNS if column in frame and frame[column].notna().any()]
    if not numeric:
        raise ValueError("No numeric anomaly features found")
    transform = ColumnTransformer(
        [
            ("numeric", Pipeline([("impute", SimpleImputer(strategy="median")), ("scale", RobustScaler())]), numeric),
            ("category", Pipeline([("impute", SimpleImputer(strategy="most_frequent")), ("encode", OneHotEncoder(handle_unknown="ignore"))]), categories),
        ]
    )
    model = IsolationForest(n_estimators=200, contamination="auto", random_state=random_state)
    values = transform.fit_transform(frame)
    raw = -model.fit(values).score_samples(values)
    order = pd.Series(raw).rank(method="average", pct=True).to_numpy() * 100
    results: list[ScoringResult] = []
    for position, (_, row) in enumerate(frame.iterrows()):
        year = row.get("fiscal_year")
        results.append(
            ScoringResult(
                project_id=str(row[IDENTIFIER_COLUMNS[0]]),
                fiscal_year=None if pd.isna(year) else int(year),
                raw_score=float(raw[position]),
                percentile=float(np.round(order[position], 2)),
            )
        )
    return results

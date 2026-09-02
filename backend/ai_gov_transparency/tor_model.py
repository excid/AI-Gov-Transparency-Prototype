"""Small reproducible pre-award Isolation Forest for TOR profile comparison."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd
import joblib
from pathlib import Path
from sklearn.ensemble import IsolationForest
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import RobustScaler

from .tor_features import PreAwardFeatures

MODEL_COLUMNS = ["log_budget", "reference_to_budget_ratio", "log_duration_days", "missing_core_field_count"]


@dataclass
class PreAwardArtifact:
    training_rows: pd.DataFrame
    max_rows: int
    random_state: int
    model_version: str = "tor-isolation-forest-0.1"


@dataclass(frozen=True)
class ModelResult:
    abstained: bool
    reason: str
    percentile: float | None = None
    raw_score: float | None = None
    model_version: str = "tor-isolation-forest-0.1"
    cohort_size: int = 0
    comparable_criteria: tuple[str, ...] = ()


def _training_features(frame: pd.DataFrame) -> pd.DataFrame:
    budget = pd.to_numeric(frame.get("project_money_baht"), errors="coerce")
    reference = pd.to_numeric(frame.get("reference_price_baht"), errors="coerce")
    duration = pd.to_numeric(frame.get("mean_contract_duration_days"), errors="coerce")
    output = pd.DataFrame(index=frame.index)
    output["log_budget"] = budget.map(lambda value: math.log1p(value) if pd.notna(value) and value >= 0 else np.nan)
    output["reference_to_budget_ratio"] = reference / budget.replace(0, np.nan)
    output["log_duration_days"] = duration.map(lambda value: math.log1p(value) if pd.notna(value) and value >= 0 else np.nan)
    output["missing_core_field_count"] = output.isna().sum(axis=1)
    return output


def fit_preaward_model(frame: pd.DataFrame, *, max_rows: int = 1000, random_state: int = 42) -> PreAwardArtifact:
    if len(frame) < 30:
        raise ValueError("ต้องมีโครงการ GovSpending อย่างน้อย 30 รายการ")
    sampled = frame.sample(n=min(max_rows, len(frame)), random_state=random_state).reset_index(drop=True)
    return PreAwardArtifact(sampled, max_rows, random_state)


def save_preaward_artifact(artifact: PreAwardArtifact, path: str | Path) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, output)
    return output


def load_preaward_artifact(path: str | Path) -> PreAwardArtifact:
    artifact = joblib.load(Path(path))
    if not isinstance(artifact, PreAwardArtifact) or artifact.model_version != "tor-isolation-forest-0.1":
        raise ValueError("ไฟล์โมเดล TOR ไม่ตรงกับสัญญารุ่นปัจจุบัน")
    return artifact


def _cohort(features: PreAwardFeatures, rows: pd.DataFrame) -> tuple[pd.DataFrame, tuple[str, ...]]:
    cohort = rows
    criteria: list[str] = []
    for column, value, label in (
        ("project_type_name", features.project_type_name, "ประเภทโครงการเดียวกัน"),
        ("purchase_method_name", features.purchase_method_name, "วิธีจัดซื้อเดียวกัน"),
    ):
        if value and column in cohort:
            narrowed = cohort[cohort[column].astype(str).str.contains(str(value), case=False, na=False)]
            if len(narrowed) >= 30:
                cohort = narrowed
                criteria.append(label)
    if features.log_budget is not None and "project_money_baht" in cohort:
        budget = math.expm1(features.log_budget)
        narrowed = cohort[pd.to_numeric(cohort["project_money_baht"], errors="coerce").between(budget * 0.5, budget * 2)]
        if len(narrowed) >= 30:
            cohort = narrowed
            criteria.append("วงเงิน 0.5x-2x")
    return cohort, tuple(criteria or ["ชุดข้อมูลรวม"])


def score_preaward(features: PreAwardFeatures, artifact: PreAwardArtifact | None) -> ModelResult:
    row = features.as_model_row()
    available = sum(row[column] is not None for column in MODEL_COLUMNS[:-1])
    if available < 2:
        return ModelResult(True, "ข้อมูลไม่พอ: ต้องมีตัวเลขก่อนประกาศอย่างน้อย 2 ตัวแปร")
    if artifact is None:
        return ModelResult(True, "ยังไม่มีโมเดล GovSpending ที่ผ่านการฝึก")
    cohort, criteria = _cohort(features, artifact.training_rows)
    matrix = _training_features(cohort)
    pipeline = Pipeline([("impute", SimpleImputer(strategy="median")), ("scale", RobustScaler())])
    transformed = pipeline.fit_transform(matrix[MODEL_COLUMNS])
    model = IsolationForest(n_estimators=150, contamination="auto", random_state=artifact.random_state)
    model.fit(transformed)
    reference_scores = -model.score_samples(transformed)
    input_frame = pd.DataFrame([{column: row[column] for column in MODEL_COLUMNS}])
    raw = float(-model.score_samples(pipeline.transform(input_frame))[0])
    percentile = round(float((reference_scores <= raw).mean() * 100), 2)
    return ModelResult(False, "", percentile, raw, artifact.model_version, len(cohort), criteria)

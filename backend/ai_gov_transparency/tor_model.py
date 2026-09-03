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
from sklearn.feature_extraction.text import TfidfVectorizer
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
class SimilarProject:
    project_id: str
    project_name: str
    department: str
    fiscal_year: int | None
    budget_baht: float | None
    purchase_method: str
    project_type: str
    duration_days: float | None
    similarity_percent: float


@dataclass(frozen=True)
class ModelResult:
    abstained: bool
    reason: str
    percentile: float | None = None
    raw_score: float | None = None
    model_version: str = "tor-isolation-forest-0.1"
    cohort_size: int = 0
    comparable_criteria: tuple[str, ...] = ()
    similar_projects: tuple[SimilarProject, ...] = ()


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
        raise ValueError("ต้องมีข้อมูล GovSpending อย่างน้อย 30 โครงการ")
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
        raise ValueError("รุ่นของแบบจำลอง TOR ไม่ตรงกับระบบ")
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
        return ModelResult(True, "ข้อมูลตัวเลขไม่พอ ต้องพบอย่างน้อย 2 รายการจากวงเงิน ราคากลาง และระยะเวลา")
    if artifact is None:
        return ModelResult(True, "ไม่พบข้อมูล GovSpending สำหรับสร้างแบบจำลอง")
    cohort, criteria = _cohort(features, artifact.training_rows)
    matrix = _training_features(cohort)
    pipeline = Pipeline([("impute", SimpleImputer(strategy="median")), ("scale", RobustScaler())])
    transformed = pipeline.fit_transform(matrix[MODEL_COLUMNS])
    model = IsolationForest(n_estimators=150, contamination="auto", random_state=artifact.random_state)
    model.fit(transformed)
    reference_scores = -model.score_samples(transformed)
    input_frame = pd.DataFrame([{column: row[column] for column in MODEL_COLUMNS}])
    input_transformed = pipeline.transform(input_frame)
    raw = float(-model.score_samples(input_transformed)[0])
    percentile = round(float((reference_scores <= raw).mean() * 100), 2)
    distances = np.linalg.norm(transformed - input_transformed[0], axis=1)
    numeric_similarity = 1 / (1 + distances)
    name_similarity = np.zeros(len(cohort))
    can_compare_name = False
    if features.project_name and "project_name" in cohort:
        names = cohort["project_name"].fillna("").astype(str).tolist()
        if any(name.strip() for name in names):
            vectorizer = TfidfVectorizer(analyzer="char", ngram_range=(2, 5), lowercase=True)
            title_matrix = vectorizer.fit_transform([*names, features.project_name])
            name_similarity = (title_matrix[:-1] @ title_matrix[-1].T).toarray().ravel()
            can_compare_name = True
    can_compare_type = features.project_type_name and "project_type_name" in cohort
    if can_compare_type:
        project_types = cohort["project_type_name"].fillna("").astype(str).str.strip().str.casefold()
        expected_type = str(features.project_type_name).strip().casefold()
        type_similarity = (project_types == expected_type).astype(float).to_numpy()
        combined_similarity = 0.5 * type_similarity + 0.4 * numeric_similarity + 0.1 * name_similarity
    else:
        combined_similarity = 0.8 * numeric_similarity + 0.2 * name_similarity if can_compare_name else numeric_similarity
    nearest_positions = np.argsort(-combined_similarity)[:3]
    similar: list[SimilarProject] = []
    for position in nearest_positions:
        project = cohort.iloc[int(position)]
        year = pd.to_numeric(project.get("fiscal_year"), errors="coerce")
        budget = pd.to_numeric(project.get("project_money_baht"), errors="coerce")
        duration = pd.to_numeric(project.get("mean_contract_duration_days"), errors="coerce")
        similar.append(SimilarProject(
            project_id=str(project.get("project_id", "ไม่ระบุ")),
            project_name=str(project.get("project_name") or "ไม่พบชื่อโครงการในชุดข้อมูล"),
            department=str(project.get("dept_name") or "ไม่ระบุหน่วยงาน"),
            fiscal_year=int(year) if pd.notna(year) else None,
            budget_baht=float(budget) if pd.notna(budget) else None,
            purchase_method=str(project.get("purchase_method_name") or "ไม่ระบุ"),
            project_type=str(project.get("project_type_name") or "ไม่ระบุ"),
            duration_days=float(duration) if pd.notna(duration) else None,
            similarity_percent=round(float(combined_similarity[int(position)] * 100), 1),
        ))
    return ModelResult(False, "", percentile, raw, artifact.model_version, len(cohort), criteria, tuple(similar))

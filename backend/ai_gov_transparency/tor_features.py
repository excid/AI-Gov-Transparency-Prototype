"""Extract pre-award features that exist in both TORs and GovSpending data."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

from .ocr import PageText
from .tor_rules import normalize_thai_digits


@dataclass(frozen=True)
class PreAwardFeatures:
    log_budget: float | None = None
    reference_to_budget_ratio: float | None = None
    log_duration_days: float | None = None
    missing_core_field_count: int = 0
    project_type_name: str | None = None
    purchase_method_name: str | None = None
    fiscal_year: int | None = None
    project_name: str | None = None
    budget_baht: float | None = None
    reference_price_baht: float | None = None
    duration_days: int | None = None

    def as_model_row(self) -> dict[str, float | int | str | None]:
        return {
            "log_budget": self.log_budget,
            "reference_to_budget_ratio": self.reference_to_budget_ratio,
            "log_duration_days": self.log_duration_days,
            "missing_core_field_count": self.missing_core_field_count,
            "project_type_name": self.project_type_name,
            "purchase_method_name": self.purchase_method_name,
            "fiscal_year": self.fiscal_year,
            "project_name": self.project_name,
        }

    def as_project_summary(self) -> dict[str, float | int | str | None]:
        return {
            "project_name": self.project_name,
            "budget_baht": self.budget_baht,
            "reference_price_baht": self.reference_price_baht,
            "duration_days": self.duration_days,
            "project_type": self.project_type_name,
            "purchase_method": self.purchase_method_name,
            "fiscal_year": self.fiscal_year,
        }


def _money(text: str, label: str) -> float | None:
    match = re.search(label + r"[^\d]{0,35}([\d,]+(?:\.\d+)?)\s*บาท", text)
    return float(match.group(1).replace(",", "")) if match else None


def extract_preaward_features(pages: list[PageText]) -> PreAwardFeatures:
    text = normalize_thai_digits("\n".join(page.text for page in pages))
    name_match = re.search(r"(?:^|\n)\s*ชื่อโครงการ\s*[:：]?\s*([^\n]{3,250})", text, re.IGNORECASE)
    budget = _money(text, r"วงเงิน(?:งบประมาณ)?")
    reference = _money(text, r"ราคากลาง")
    duration_match = re.search(r"(?:ระยะเวลา(?:ดำเนินการ|ก่อสร้าง)?|ภายใน)[^\d]{0,30}(\d+)\s*วัน", text)
    duration = int(duration_match.group(1)) if duration_match else None
    method = "e-bidding" if re.search(r"e-?bidding|ประกวดราคาอิเล็กทรอนิกส์", text, re.IGNORECASE) else None
    project_type = "งานก่อสร้าง" if re.search(r"ก่อสร้าง|อาคาร|ถนน|สะพาน", text) else None
    year_match = re.search(r"(?:พ\.?ศ\.?|ปีงบประมาณ)(?:\s*พ\.?ศ\.?)?\s*(25\d{2})", text)
    missing = sum(value is None for value in (budget, reference, duration, method))
    return PreAwardFeatures(
        log_budget=math.log1p(budget) if budget is not None else None,
        reference_to_budget_ratio=(reference / budget) if reference is not None and budget else None,
        log_duration_days=math.log1p(duration) if duration is not None else None,
        missing_core_field_count=missing,
        project_type_name=project_type,
        purchase_method_name=method,
        fiscal_year=int(year_match.group(1)) if year_match else None,
        project_name=name_match.group(1).strip(" :-–—") if name_match else None,
        budget_baht=budget,
        reference_price_baht=reference,
        duration_days=duration,
    )

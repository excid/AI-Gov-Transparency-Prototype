"""Deterministic, evidence-preserving rules for Thai TOR screening."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .ocr import PageText

THAI_DIGITS = str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789")


@dataclass(frozen=True)
class Finding:
    category: str
    severity: str
    source: str
    evidence: str
    page: int
    reason: str
    confidence: float
    details: dict[str, Any] = field(default_factory=dict)


def normalize_thai_digits(text: str) -> str:
    return text.translate(THAI_DIGITS)


def _number(value: str) -> float:
    return float(value.replace(",", ""))


def _excerpt(text: str, start: int, end: int, radius: int = 90) -> str:
    paragraph_start = text.rfind("\n\n", 0, start)
    paragraph_end = text.find("\n\n", end)
    if paragraph_start < 0:
        paragraph_start = 0
    else:
        paragraph_start += 2
    if paragraph_end < 0:
        paragraph_end = len(text)
    return re.sub(r"\s+", " ", text[paragraph_start:paragraph_end]).strip()


def evaluate_rules(pages: list[PageText]) -> list[Finding]:
    findings: list[Finding] = []
    budget: float | None = None
    for page in pages:
        text = normalize_thai_digits(page.text)
        budget_match = re.search(r"วงเงิน(?:งบประมาณ)?[^\d]{0,35}([\d,]+(?:\.\d+)?)\s*บาท", text)
        if budget_match and budget is None:
            budget = _number(budget_match.group(1))

    for page in pages:
        text = normalize_thai_digits(page.text)
        confidence = max(0.45, page.quality)

        previous = re.search(r"(?:ผลงาน|ประสบการณ์)[\s\S]{0,120}?(?:ไม่น้อยกว่า|ขั้นต่ำ)[^\d]{0,25}([\d,]+(?:\.\d+)?)\s*บาท", text)
        if previous and budget:
            value = _number(previous.group(1))
            ratio = value / budget * 100
            if ratio >= 50:
                findings.append(Finding("previous_work_percentage", "high" if ratio >= 80 else "medium", "rule", _excerpt(text, *previous.span()), page.page_number, f"กำหนดมูลค่าผลงานเดิมประมาณ {ratio:.1f}% ของวงเงินโครงการ", confidence, {"required_previous_work": value, "project_budget": budget, "ratio_percent": ratio}))

        brand = re.search(r"(?:ยี่ห้อ|ตราสินค้า|รุ่น)\s*[A-Za-z0-9ก-๙._/-]{2,}(?:[\s\S]{0,45}(?:เท่านั้น|ห้ามใช้เทียบเท่า))?", text, re.IGNORECASE)
        if brand:
            allows = bool(re.search(r"หรือเทียบเท่า", _excerpt(text, *brand.span(), 120))) and not bool(re.search(r"ห้ามใช้เทียบเท่า", _excerpt(text, *brand.span(), 120)))
            if not allows:
                findings.append(Finding("brand_specific", "high", "rule", _excerpt(text, *brand.span()), page.page_number, "ระบุยี่ห้อหรือรุ่นโดยไม่เปิดทางให้ใช้ของเทียบเท่า", confidence))

        certificate = re.search(r"(?:ใบรับรอง|มาตรฐาน)\s*(?:ISO|มอก\.?|[A-Z]{2,})?\s*[\dA-Za-z./:-]{2,}", text, re.IGNORECASE)
        if certificate:
            findings.append(Finding("unnecessary_certificate", "medium", "rule", _excerpt(text, *certificate.span()), page.page_number, "พบข้อกำหนดใบรับรองเฉพาะ ต้องให้ผู้ตรวจประเมินความจำเป็นกับลักษณะงาน", confidence * 0.9))

        constraints = list(re.finditer(r"(?:ไม่น้อยกว่า|ไม่เกิน|อย่างน้อย|ขนาด|ความจุ|สูง)\s*[\d,.]+\s*(?:ชั้น|เมตร|มม\.?|กก\.?|ตัน|หน่วย|ระบบ|โครงการ)?", text))
        technologies = re.findall(r"Post[- ]?Tension|ลิฟต์ดับเพลิง|ชั้นใต้ดิน", text, re.IGNORECASE)
        if len(constraints) + len(technologies) >= 3:
            first = constraints[0].span() if constraints else (0, min(len(text), 80))
            findings.append(Finding("narrow_technical_requirement", "medium", "rule", _excerpt(text, *first, 160), page.page_number, f"พบเงื่อนไขทางเทคนิคที่ใช้ร่วมกัน {len(constraints) + len(technologies)} รายการ", confidence * 0.9, {"constraint_count": len(constraints) + len(technologies)}))

        personnel = re.search(r"(?:ผู้อำนวยการโครงการ|ผู้ควบคุมงาน|วิศวกร|บุคลากร)[\s\S]{0,150}?(?:ประสบการณ์|ไม่น้อยกว่า)[^\d]{0,20}(\d+)\s*ปี(?:[\s\S]{0,100}?(\d+)\s*โครงการ)?", text)
        if personnel:
            years = int(personnel.group(1))
            projects = int(personnel.group(2)) if personnel.group(2) else None
            if years >= 10 or (projects or 0) >= 3:
                findings.append(Finding("experience_or_personnel", "high" if years >= 20 else "medium", "rule", _excerpt(text, *personnel.span()), page.page_number, "กำหนดประสบการณ์บุคลากรในระดับที่อาจจำกัดการแข่งขัน", confidence, {"minimum_years": years, "minimum_projects": projects}))

        restrictive = re.search(r"(?:ซึ่งเป็นสัญญาเดียวกัน|ต้องเป็นสัญญาเดียวกัน|เฉพาะผู้ที่|ห้ามใช้เทียบเท่า)", text)
        if restrictive:
            findings.append(Finding("other_lock_spec", "medium", "rule", _excerpt(text, *restrictive.span()), page.page_number, "พบถ้อยคำจำกัดเงื่อนไขที่ควรตรวจสอบบริบทเพิ่มเติม", confidence))

    unique: dict[tuple[str, int, str], Finding] = {}
    for finding in findings:
        unique[(finding.category, finding.page, finding.evidence)] = finding
    return list(unique.values())

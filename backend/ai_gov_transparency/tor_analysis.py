"""Orchestrate TOR rules, LLM interpretation, and pre-award anomaly scoring."""

from __future__ import annotations

import os
from dataclasses import asdict
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

from .ocr import PageText, document_id, extract_pdf_pages
from .tor_features import extract_preaward_features
from .tor_llm import LlmResult, analyze_with_llm
from .tor_model import PreAwardArtifact, load_preaward_artifact, score_preaward
from .tor_rules import Finding, evaluate_rules
from .local_ocr import local_paddle_pages


@lru_cache(maxsize=1)
def load_model_artifact() -> PreAwardArtifact | None:
    path = os.getenv("TOR_MODEL_PATH", "data/models/tor-isolation-forest.joblib")
    return load_preaward_artifact(path) if Path(path).is_file() else None


def _finding_dict(finding: Finding) -> dict[str, Any]:
    return asdict(finding)


def _deduplicate(findings: list[Finding]) -> list[Finding]:
    ranked = {"rule": 0, "llm": 1}
    ordered = sorted(findings, key=lambda item: (item.page, item.category, ranked.get(item.source, 9)))
    unique: dict[tuple[str, int], Finding] = {}
    for finding in ordered:
        unique.setdefault((finding.category, finding.page), finding)
    return list(unique.values())


def analyze_pages(
    pages: list[PageText],
    *,
    llm_result: LlmResult | None,
    model_artifact: PreAwardArtifact | None,
) -> dict[str, Any]:
    rules = evaluate_rules(pages)
    features = extract_preaward_features(pages)
    model = score_preaward(features, model_artifact)
    warnings: list[str] = []
    if llm_result is None:
        warnings.append("LLM ไม่พร้อมใช้งาน ผลลัพธ์ยังมีการตรวจด้วยกฎและ ML")
    if model.abstained:
        warnings.append(f"ML งดให้คะแนน: {model.reason}")
    if any(page.quality < 0.5 for page in pages):
        warnings.append("บางหน้ามีคุณภาพ OCR ต่ำ ควรเปิด PDF ตรวจข้อความต้นฉบับ")
    combined = _deduplicate(rules + (list(llm_result.findings) if llm_result else []))
    return {
        "status": "completed_with_warnings" if warnings else "completed",
        "summary": llm_result.summary if llm_result else "ผลคัดกรองเบื้องต้นจากข้อความ TOR",
        "pageCount": len(pages),
        "ocrPages": sum(page.ocr_used for page in pages),
        "findings": [_finding_dict(item) for item in combined],
        "features": features.as_model_row(),
        "model": asdict(model),
        "warnings": warnings,
        "disclaimer": "เป็นสัญญาณเพื่อจัดลำดับการตรวจสอบ ไม่ใช่ข้อสรุปว่ามีการทุจริต",
    }


def analyze_tor(
    payload: bytes,
    *,
    on_progress: Callable[[str, int], None] | None = None,
) -> dict[str, Any]:
    report = on_progress or (lambda _stage, _percent: None)
    report("ocr", 15)
    pages = extract_pdf_pages(payload, ocr_pages=local_paddle_pages)
    report("llm", 60)
    try:
        llm = analyze_with_llm(pages)
    except Exception:
        llm = None
    report("screening", 90)
    model_artifact = load_model_artifact()
    result = analyze_pages(pages, llm_result=llm, model_artifact=model_artifact)
    result["documentId"] = document_id(payload)
    report("complete", 100)
    return result

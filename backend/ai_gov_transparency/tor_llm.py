"""Strict Alibaba Qwen analysis with graceful, auditable failure."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass

import httpx

from .ocr import PageText
from .tor_rules import Finding

ALLOWED_CATEGORIES = {
    "previous_work_percentage", "brand_specific", "unnecessary_certificate",
    "narrow_technical_requirement", "experience_or_personnel", "other_lock_spec",
}
ALLOWED_SEVERITIES = {"low", "medium", "high"}
THAI_TEXT = re.compile(r"[ก-๙]")


class LlmSchemaError(ValueError):
    pass


@dataclass(frozen=True)
class LlmResult:
    summary: str
    findings: tuple[Finding, ...]
    model: str = "qwen3.8-flash"


def parse_llm_content(content: str) -> LlmResult:
    try:
        value = json.loads(content)
        summary = str(value["summary"]).strip()
        rows = value["findings"]
    except (json.JSONDecodeError, KeyError, TypeError) as error:
        raise LlmSchemaError("LLM ส่งข้อมูลผิดรูปแบบ") from error
    if not isinstance(rows, list) or not summary:
        raise LlmSchemaError("คำตอบจาก LLM ไม่มีสรุปหรือรายการตรวจพบ")
    if not THAI_TEXT.search(summary):
        raise LlmSchemaError("LLM ต้องเขียนสรุปเป็นภาษาไทย")
    findings: list[Finding] = []
    for row in rows[:20]:
        if not isinstance(row, dict) or row.get("category") not in ALLOWED_CATEGORIES or row.get("severity") not in ALLOWED_SEVERITIES:
            raise LlmSchemaError("LLM ส่งหมวดหรือระดับที่ระบบไม่รองรับ")
        evidence = str(row.get("evidence", "")).strip()
        reason = str(row.get("reason", "")).strip()
        page = int(row.get("page", 0))
        confidence = float(row.get("confidence", 0))
        if not evidence or not reason or page < 1 or not 0 <= confidence <= 1:
            raise LlmSchemaError("รายการจาก LLM ไม่มีหลักฐาน เหตุผล เลขหน้า หรือค่าความมั่นใจ")
        if not THAI_TEXT.search(reason):
            raise LlmSchemaError("LLM ต้องเขียนเหตุผลเป็นภาษาไทย")
        findings.append(Finding(str(row["category"]), str(row["severity"]), "llm", evidence, page, reason, confidence))
    return LlmResult(summary, tuple(findings))


def analyze_with_llm(pages: list[PageText], *, timeout_seconds: float = 240) -> LlmResult | None:
    api_key = os.getenv("LLM_API_KEY")
    base_url = os.getenv("LLM_BASE_URL", "").rstrip("/")
    if not api_key or not base_url:
        return None
    page_text = "\n\n".join(f"[PAGE {page.page_number}]\n{page.text}" for page in pages)[:160_000]
    system = (
        "You screen Thai TOR documents for competition-limiting clauses, not corruption. "
        "Return compact JSON with summary and findings. Allowed categories: " + ", ".join(sorted(ALLOWED_CATEGORIES)) + ". "
        "Each finding requires category, severity low|medium|high, exact evidence quoted from the supplied page, page, reason, confidence 0..1. "
        "The summary and reason must be written in Thai. The evidence must remain an exact quote in its original language from the document. "
        "Use concise, natural Thai. Write each summary and reason as one sentence. Avoid slogans, filler, repetition, and translated-sounding phrasing. "
        "Do not translate or paraphrase evidence. Do not flag normal procurement/legal requirements without document-specific restrictive evidence. "
        "Separate quotation from interpretation."
    )
    response = httpx.post(
        f"{base_url}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": os.getenv("LLM_MODEL", "qwen3.8-flash"),
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": page_text}],
            "temperature": 0,
            "max_tokens": 4000,
            "response_format": {"type": "json_object"},
        },
        timeout=timeout_seconds,
    )
    response.raise_for_status()
    body = response.json()
    return parse_llm_content(body["choices"][0]["message"]["content"])

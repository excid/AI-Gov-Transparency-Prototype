"""Page-preserving local text extraction for uploaded TOR PDFs."""

from __future__ import annotations

import hashlib
import io
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass(frozen=True)
class PageText:
    page_number: int
    text: str
    ocr_used: bool
    quality: float


class PdfExtractionError(ValueError):
    pass


def extract_pdf_pages(
    payload: bytes,
    *,
    max_pages: int = 100,
    ocr_page: Callable[[bytes, int], str] | None = None,
    ocr_pages: Callable[[bytes, list[int]], dict[int, str]] | None = None,
) -> list[PageText]:
    """Extract embedded text and bulk-OCR only pages that need recognition."""
    if not payload.startswith(b"%PDF"):
        raise PdfExtractionError("ไฟล์ที่อัปโหลดไม่ใช่ PDF")
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(payload))
    except Exception as error:
        raise PdfExtractionError("ไม่สามารถเปิดไฟล์ PDF ได้") from error
    if reader.is_encrypted:
        raise PdfExtractionError("ไม่รองรับ PDF ที่เข้ารหัส")
    if not reader.pages:
        raise PdfExtractionError("PDF ไม่มีหน้าเอกสาร")
    if len(reader.pages) > max_pages:
        raise PdfExtractionError(f"PDF ต้องมีไม่เกิน {max_pages} หน้า")

    extracted: list[str] = []
    for index, page in enumerate(reader.pages, start=1):
        embedded = (page.extract_text() or "").strip()
        extracted.append(embedded)

    missing = [index for index, text in enumerate(extracted, start=1) if len(text) < 40]
    recognized = ocr_pages(payload, missing) if missing and ocr_pages is not None else {}

    results: list[PageText] = []
    for index, embedded in enumerate(extracted, start=1):
        used = index in missing and (ocr_pages is not None or ocr_page is not None)
        text = recognized.get(index, "").strip() if index in missing else embedded
        if index in missing and not text and ocr_page is not None:
            text = ocr_page(payload, index).strip()
        visible = sum(character.isalnum() for character in text)
        quality = round(min(1.0, visible / 80), 2)
        results.append(PageText(index, text, used, quality))
    if not any(page.text.strip() for page in results):
        raise PdfExtractionError("ไม่พบข้อความใน PDF และ OCR ไม่ได้ผล")
    return results


def local_tesseract_page(payload: bytes, page_number: int) -> str:
    """Render one page with local Poppler and OCR it with local Tesseract."""
    try:
        import pytesseract
        from pdf2image import convert_from_bytes

        command = resolve_tesseract_command()
        if command is None:
            raise FileNotFoundError("ไม่พบ Tesseract OCR ในเครื่อง")
        pytesseract.pytesseract.tesseract_cmd = str(command)
        # 150 DPI is sufficient for a presentation prototype and avoids turning
        # ordinary scanned TORs into multi-minute, gigabyte-heavy OCR jobs.
        dpi = int(os.getenv("OCR_DPI", "150"))
        psm = os.getenv("OCR_PSM", "6")
        image = convert_from_bytes(payload, dpi=dpi, first_page=page_number, last_page=page_number, fmt="png")[0]
        return pytesseract.image_to_string(image, lang="tha+eng", config=f"--psm {psm}")
    except Exception as error:
        raise PdfExtractionError(f"OCR หน้า {page_number} ไม่สำเร็จ: {error}") from error


def resolve_tesseract_command(candidates: list[Path] | None = None) -> Path | None:
    configured = os.getenv("TESSERACT_CMD")
    defaults = [
        Path(configured) if configured else None,
        Path(shutil.which("tesseract")) if shutil.which("tesseract") else None,
        Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
    ]
    for path in candidates if candidates is not None else defaults:
        if path is not None and path.is_file():
            return path
    return None


def document_id(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()[:16]

"""Page-complete local Thai OCR with PaddleOCR and Tesseract fallback."""

from __future__ import annotations

import io
import os
from collections.abc import Callable, Iterable
from functools import lru_cache
from typing import Any

from .ocr import PdfExtractionError, local_tesseract_page

BatchAnnotator = Callable[[list[tuple[int, bytes]]], dict[int, str]]


def recognize_images_in_batches(
    images: dict[int, bytes],
    *,
    annotate: BatchAnnotator,
    batch_size: int = 4,
) -> dict[int, str]:
    """Recognize every possible page and isolate batch failures per page."""
    ordered = sorted(images.items())
    result: dict[int, str] = {}
    for start in range(0, len(ordered), batch_size):
        batch = ordered[start:start + batch_size]
        try:
            result.update(annotate(batch))
        except Exception:
            for item in batch:
                try:
                    result.update(annotate([item]))
                except Exception:
                    continue
    return {page: text.strip() for page, text in result.items() if text.strip()}


def _result_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    serialized = getattr(value, "json", None)
    if callable(serialized):
        serialized = serialized()
    return serialized if isinstance(serialized, dict) else {}


def extract_paddle_text(results: Iterable[Any]) -> str:
    """Normalize PaddleOCR result objects without discarding recognized lines."""
    lines: list[str] = []
    for item in results:
        value = _result_mapping(item)
        payload = value.get("res", value)
        texts = payload.get("rec_texts", []) if isinstance(payload, dict) else []
        if isinstance(texts, list):
            lines.extend(str(text).strip() for text in texts if str(text).strip())
        elif isinstance(payload, dict) and str(payload.get("rec_text", "")).strip():
            lines.append(str(payload["rec_text"]).strip())
    return "\n".join(lines)


def _render_pages(payload: bytes, page_numbers: list[int]) -> dict[int, bytes]:
    from pdf2image import convert_from_bytes

    dpi = int(os.getenv("OCR_RENDER_DPI", "180"))
    quality = int(os.getenv("OCR_JPEG_QUALITY", "88"))
    images: dict[int, bytes] = {}
    for start in range(0, len(page_numbers), 8):
        chunk = page_numbers[start:start + 8]
        groups: list[list[int]] = []
        for page in chunk:
            if groups and page == groups[-1][-1] + 1:
                groups[-1].append(page)
            else:
                groups.append([page])
        for group in groups:
            rendered = convert_from_bytes(
                payload,
                dpi=dpi,
                first_page=group[0],
                last_page=group[-1],
                fmt="jpeg",
                jpegopt={"quality": quality, "optimize": True},
                thread_count=min(4, len(group)),
            )
            for page, image in zip(group, rendered, strict=True):
                buffer = io.BytesIO()
                image.save(buffer, format="JPEG", quality=quality, optimize=True)
                images[page] = buffer.getvalue()
    return images


@lru_cache(maxsize=1)
def _paddle_pipeline():
    from paddleocr import PaddleOCR

    return PaddleOCR(
        lang="th",
        ocr_version="PP-OCRv5",
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=True,
        device="cpu",
    )


def _paddle_annotator() -> BatchAnnotator:
    import numpy as np
    from PIL import Image

    pipeline = _paddle_pipeline()

    def annotate(batch: list[tuple[int, bytes]]) -> dict[int, str]:
        texts: dict[int, str] = {}
        for page, content in batch:
            image = np.asarray(Image.open(io.BytesIO(content)).convert("RGB"))
            text = extract_paddle_text(pipeline.predict(image))
            if text:
                texts[page] = text
        return texts

    return annotate


def local_paddle_pages(payload: bytes, page_numbers: list[int]) -> dict[int, str]:
    """OCR requested pages locally; use Tesseract only for Paddle misses."""
    if not page_numbers:
        return {}
    try:
        recognized = recognize_images_in_batches(_render_pages(payload, page_numbers), annotate=_paddle_annotator())
    except Exception:
        recognized = {}
    for page in page_numbers:
        if page in recognized:
            continue
        try:
            text = local_tesseract_page(payload, page).strip()
            if text:
                recognized[page] = text
        except PdfExtractionError:
            continue
    return recognized

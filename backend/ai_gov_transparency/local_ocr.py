"""Page-complete local Thai OCR with PaddleOCR and Tesseract fallback."""

from __future__ import annotations

import io
import hashlib
import os
from collections import OrderedDict
from collections.abc import Callable, Iterable
from functools import lru_cache
from threading import Lock
from typing import Any

from .ocr import PdfExtractionError, local_tesseract_page

BatchAnnotator = Callable[[list[tuple[int, bytes]]], dict[int, str]]
OCR_PIPELINE_VERSION = "paddle-th-v2-png-confidence"
_OCR_CACHE: OrderedDict[str, dict[int, str]] = OrderedDict()
_OCR_CACHE_LOCK = Lock()


def ocr_cache_key(payload: bytes, pipeline_version: str = OCR_PIPELINE_VERSION) -> str:
    return hashlib.sha256(pipeline_version.encode("utf-8") + b"\0" + payload).hexdigest()


def clear_ocr_cache() -> None:
    with _OCR_CACHE_LOCK:
        _OCR_CACHE.clear()


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


def extract_paddle_confidence(results: Iterable[Any]) -> float:
    """Return character-weighted line confidence from Paddle results."""
    weighted = 0.0
    characters = 0
    for item in results:
        value = _result_mapping(item)
        payload = value.get("res", value)
        if not isinstance(payload, dict):
            continue
        texts = payload.get("rec_texts", [])
        scores = payload.get("rec_scores", [])
        if not isinstance(texts, list) or not isinstance(scores, list):
            continue
        for text, score in zip(texts, scores):
            length = max(1, len(str(text).strip()))
            try:
                weighted += float(score) * length
                characters += length
            except (TypeError, ValueError):
                continue
    return weighted / characters if characters else 0.0


def _render_pages(payload: bytes, page_numbers: list[int]) -> dict[int, bytes]:
    from pdf2image import convert_from_bytes

    dpi = int(os.getenv("OCR_RENDER_DPI", "240"))
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
                fmt="png",
                thread_count=min(4, len(group)),
            )
            for page, image in zip(group, rendered, strict=True):
                from PIL import ImageEnhance, ImageFilter, ImageOps

                image = ImageOps.autocontrast(ImageOps.grayscale(image))
                image = ImageEnhance.Contrast(image).enhance(float(os.getenv("OCR_CONTRAST", "1.25")))
                image = image.filter(ImageFilter.SHARPEN)
                buffer = io.BytesIO()
                image.save(buffer, format="PNG", optimize=True)
                images[page] = buffer.getvalue()
    return images


@lru_cache(maxsize=2)
def _paddle_pipeline(device: str):
    from paddleocr import PaddleOCR

    return PaddleOCR(
        lang="th",
        ocr_version="PP-OCRv5",
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=True,
        device=device,
    )


def _preferred_device() -> str:
    configured = os.getenv("OCR_DEVICE", "auto").strip().lower()
    if configured != "auto":
        return configured
    try:
        import paddle

        return "gpu:0" if paddle.device.is_compiled_with_cuda() else "cpu"
    except Exception:
        return "cpu"


def _paddle_annotator(device: str) -> BatchAnnotator:
    import numpy as np
    from PIL import Image

    pipeline = _paddle_pipeline(device)
    minimum_confidence = float(os.getenv("OCR_MIN_CONFIDENCE", "0.72"))

    def annotate(batch: list[tuple[int, bytes]]) -> dict[int, str]:
        texts: dict[int, str] = {}
        for page, content in batch:
            image = np.asarray(Image.open(io.BytesIO(content)).convert("RGB"))
            results = list(pipeline.predict(image))
            text = extract_paddle_text(results)
            if text and extract_paddle_confidence(results) >= minimum_confidence:
                texts[page] = text
        return texts

    return annotate


def _recognize_pages_uncached(payload: bytes, page_numbers: list[int]) -> dict[int, str]:
    images = _render_pages(payload, page_numbers)
    device = _preferred_device()
    try:
        recognized = recognize_images_in_batches(images, annotate=_paddle_annotator(device))
    except Exception:
        recognized = {}
        if device != "cpu":
            try:
                recognized = recognize_images_in_batches(images, annotate=_paddle_annotator("cpu"))
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


def local_paddle_pages(payload: bytes, page_numbers: list[int]) -> dict[int, str]:
    """OCR requested pages locally; cache text only and never retain PDF bytes."""
    if not page_numbers:
        return {}
    ordered_pages = sorted(set(page_numbers))
    key = f"{ocr_cache_key(payload)}:{','.join(map(str, ordered_pages))}"
    with _OCR_CACHE_LOCK:
        cached = _OCR_CACHE.get(key)
        if cached is not None:
            _OCR_CACHE.move_to_end(key)
            return dict(cached)
    recognized = _recognize_pages_uncached(payload, ordered_pages)
    with _OCR_CACHE_LOCK:
        _OCR_CACHE[key] = dict(recognized)
        _OCR_CACHE.move_to_end(key)
        while len(_OCR_CACHE) > int(os.getenv("OCR_CACHE_ENTRIES", "16")):
            _OCR_CACHE.popitem(last=False)
    return recognized

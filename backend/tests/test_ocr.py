import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from pypdf import PdfWriter

from ai_gov_transparency.ocr import embedded_text_is_reliable, extract_pdf_pages, resolve_tesseract_command
from ai_gov_transparency.local_ocr import (
    extract_paddle_confidence,
    extract_paddle_text,
    ocr_cache_key,
    clear_ocr_cache,
    local_paddle_pages,
    recognize_images_in_batches,
    _render_pages,
)


class OcrRuntimeTests(unittest.TestCase):
    def test_embedded_text_rejects_garbled_content_even_when_long(self):
        self.assertFalse(embedded_text_is_reliable("� □ \x00 " * 30))

    def test_embedded_text_accepts_readable_thai_tor_content(self):
        text = "ขอบเขตของงานและคุณลักษณะเฉพาะ วงเงินงบประมาณ 1,000,000 บาท"
        self.assertTrue(embedded_text_is_reliable(text))

    def test_resolves_first_existing_tesseract_binary(self):
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / "tesseract.exe"
            executable.touch()
            self.assertEqual(resolve_tesseract_command([Path(directory) / "missing.exe", executable]), executable)

    def test_bulk_ocr_preserves_pdf_page_numbers(self):
        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        writer.add_blank_page(width=100, height=100)
        stream = io.BytesIO()
        writer.write(stream)

        seen: list[int] = []

        def ocr_pages(_payload: bytes, page_numbers: list[int]) -> dict[int, str]:
            seen.extend(page_numbers)
            return {1: "ข้อความหน้าแรก", 2: "second page text"}

        pages = extract_pdf_pages(stream.getvalue(), ocr_pages=ocr_pages)

        self.assertEqual(seen, [1, 2])
        self.assertEqual([(page.page_number, page.text, page.ocr_used) for page in pages], [
            (1, "ข้อความหน้าแรก", True),
            (2, "second page text", True),
        ])

    def test_failed_batch_retries_each_page_without_losing_successes(self):
        calls: list[list[int]] = []

        def annotate(batch: list[tuple[int, bytes]]) -> dict[int, str]:
            pages = [page for page, _image in batch]
            calls.append(pages)
            if len(batch) > 1:
                raise RuntimeError("batch failed")
            if pages == [2]:
                raise RuntimeError("page failed")
            return {pages[0]: f"text-{pages[0]}"}

        result = recognize_images_in_batches(
            {1: b"one", 2: b"two", 3: b"three"},
            annotate=annotate,
            batch_size=3,
        )

        self.assertEqual(result, {1: "text-1", 3: "text-3"})
        self.assertEqual(calls, [[1, 2, 3], [1], [2], [3]])

    def test_extracts_complete_text_lines_from_paddle_result(self):
        result = [{"res": {"rec_texts": ["ข้อกำหนด", "ภาษาไทย และ English"], "rec_scores": [0.98, 0.93]}}]

        self.assertEqual(extract_paddle_text(result), "ข้อกำหนด\nภาษาไทย และ English")

    def test_extracts_weighted_paddle_confidence(self):
        result = [{"res": {"rec_texts": ["ยาวมาก", "สั้น"], "rec_scores": [0.9, 0.3]}}]

        self.assertAlmostEqual(extract_paddle_confidence(result), 0.66, places=2)

    def test_cache_key_changes_with_payload_or_pipeline_version(self):
        first = ocr_cache_key(b"pdf-one", "v1")

        self.assertEqual(first, ocr_cache_key(b"pdf-one", "v1"))
        self.assertNotEqual(first, ocr_cache_key(b"pdf-two", "v1"))
        self.assertNotEqual(first, ocr_cache_key(b"pdf-one", "v2"))

    def test_local_ocr_cache_avoids_reprocessing_same_pages(self):
        clear_ocr_cache()
        with patch(
            "ai_gov_transparency.local_ocr._recognize_pages_uncached",
            return_value={1: "ข้อความ"},
        ) as recognize:
            first = local_paddle_pages(b"%PDF-cache", [1])
            second = local_paddle_pages(b"%PDF-cache", [1])

        self.assertEqual(first, second)
        self.assertEqual(recognize.call_count, 1)

    def test_scanned_pages_render_as_preprocessed_png_at_240_dpi(self):
        image = Image.new("RGB", (20, 20), "white")
        with patch("pdf2image.convert_from_bytes", return_value=[image]) as convert:
            rendered = _render_pages(b"%PDF-render", [1])

        self.assertEqual(rendered[1][:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(Image.open(io.BytesIO(rendered[1])).mode, "L")
        self.assertEqual(convert.call_args.kwargs["dpi"], 240)
        self.assertEqual(convert.call_args.kwargs["fmt"], "png")


if __name__ == "__main__":
    unittest.main()

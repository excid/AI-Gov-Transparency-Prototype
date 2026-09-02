import io
import tempfile
import unittest
from pathlib import Path

from pypdf import PdfWriter

from ai_gov_transparency.ocr import extract_pdf_pages, resolve_tesseract_command
from ai_gov_transparency.local_ocr import extract_paddle_text, recognize_images_in_batches


class OcrRuntimeTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()

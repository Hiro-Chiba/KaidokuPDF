"""統合テスト（Tesseract必須）。"""

from __future__ import annotations

from threading import Event

import pytest

from image_pdf_ocr import (
    OCRCancelledError,
    create_searchable_pdf,
    create_searchable_pdf_from_images,
    extract_text_from_image_pdf,
    extract_text_to_file,
)

from .conftest import requires_tesseract


@requires_tesseract
class TestCreateSearchablePdf:
    def test_generates_output_pdf(self, tmp_path, sample_image_pdf):
        output = tmp_path / "output.pdf"
        create_searchable_pdf(sample_image_pdf, output)
        assert output.exists()
        assert output.stat().st_size > 0

    def test_multi_page_pdf(self, tmp_path, sample_multi_page_pdf):
        import fitz

        output = tmp_path / "output_multi.pdf"
        create_searchable_pdf(sample_multi_page_pdf, output)
        assert output.exists()
        with fitz.open(str(output)) as doc:
            assert doc.page_count == 3

    def test_progress_callback(self, tmp_path, sample_image_pdf):
        output = tmp_path / "output_progress.pdf"
        messages = []
        create_searchable_pdf(sample_image_pdf, output, progress_callback=messages.append)
        assert len(messages) > 0

    def test_cancel_event(self, tmp_path, sample_image_pdf):
        output = tmp_path / "output_cancel.pdf"
        cancel = Event()
        cancel.set()
        with pytest.raises(OCRCancelledError):
            create_searchable_pdf(sample_image_pdf, output, cancel_event=cancel)


@requires_tesseract
class TestCreateSearchablePdfFromImages:
    def test_single_image(self, tmp_path, sample_image_with_text):
        output = tmp_path / "from_images.pdf"
        create_searchable_pdf_from_images([sample_image_with_text], output)
        assert output.exists()
        assert output.stat().st_size > 0

    def test_multiple_images(self, tmp_path, sample_images):
        import fitz

        output = tmp_path / "from_multi_images.pdf"
        create_searchable_pdf_from_images(sample_images, output)
        assert output.exists()
        with fitz.open(str(output)) as doc:
            assert doc.page_count == 3


@requires_tesseract
class TestExtractTextFromImagePdf:
    def test_extracts_text(self, sample_image_pdf):
        text = extract_text_from_image_pdf(sample_image_pdf)
        assert isinstance(text, str)
        assert len(text) > 0


@requires_tesseract
class TestExtractTextToFile:
    def test_writes_output_file(self, tmp_path, sample_image_pdf):
        output = tmp_path / "extracted.txt"
        extract_text_to_file(sample_image_pdf, output)
        assert output.exists()
        content = output.read_text(encoding="utf-8")
        assert len(content) > 0

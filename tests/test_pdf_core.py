"""_pdf.py 中核関数のユニットテスト（mock活用でTesseract不要）。"""

from __future__ import annotations

from pathlib import Path
from threading import Event
from unittest.mock import MagicMock, patch

import pytest

from image_pdf_ocr._exceptions import OCRCancelledError, OCRConversionError


class TestCreateSearchablePdf:
    """create_searchable_pdf のテスト。"""

    def test_input_not_found(self, tmp_path: Path) -> None:
        """入力ファイルが存在しない場合 FileNotFoundError。"""
        from image_pdf_ocr._pdf import create_searchable_pdf

        missing = tmp_path / "missing.pdf"
        output = tmp_path / "output.pdf"

        with (
            patch("image_pdf_ocr._pdf.find_and_set_tesseract_path", return_value=True),
            pytest.raises(FileNotFoundError, match="入力ファイルが見つかりません"),
        ):
            create_searchable_pdf(missing, output)

    def test_output_dir_created(self, tmp_path: Path) -> None:
        """出力ディレクトリが自動作成される。"""
        from image_pdf_ocr._pdf import create_searchable_pdf

        input_file = tmp_path / "input.pdf"
        input_file.write_bytes(b"%PDF-1.4 dummy")
        output = tmp_path / "sub" / "deep" / "output.pdf"

        mock_doc = MagicMock()
        mock_doc.page_count = 0
        mock_doc.__enter__ = MagicMock(return_value=mock_doc)
        mock_doc.__exit__ = MagicMock(return_value=False)
        mock_doc.__iter__ = MagicMock(return_value=iter([]))

        mock_output_doc = MagicMock()
        mock_output_doc.__enter__ = MagicMock(return_value=mock_output_doc)
        mock_output_doc.__exit__ = MagicMock(return_value=False)

        with (
            patch("image_pdf_ocr._pdf.find_and_set_tesseract_path", return_value=True),
            patch(
                "image_pdf_ocr._pdf._find_japanese_font_path", return_value=Path("/fake/font.ttf")
            ),
            patch("image_pdf_ocr._pdf.fitz") as mock_fitz,
        ):
            mock_fitz.open.side_effect = [mock_doc, mock_output_doc]
            create_searchable_pdf(input_file, output)

        assert output.parent.exists()

    def test_empty_pdf_progress_message(self, tmp_path: Path) -> None:
        """0ページPDFの進捗メッセージが送信される。"""
        from image_pdf_ocr._pdf import create_searchable_pdf

        input_file = tmp_path / "input.pdf"
        input_file.write_bytes(b"%PDF-1.4 dummy")
        output = tmp_path / "output.pdf"

        mock_doc = MagicMock()
        mock_doc.page_count = 0
        mock_doc.__enter__ = MagicMock(return_value=mock_doc)
        mock_doc.__exit__ = MagicMock(return_value=False)

        mock_output_doc = MagicMock()
        mock_output_doc.__enter__ = MagicMock(return_value=mock_output_doc)
        mock_output_doc.__exit__ = MagicMock(return_value=False)

        progress_messages: list[str] = []

        with (
            patch("image_pdf_ocr._pdf.find_and_set_tesseract_path", return_value=True),
            patch(
                "image_pdf_ocr._pdf._find_japanese_font_path", return_value=Path("/fake/font.ttf")
            ),
            patch("image_pdf_ocr._pdf.fitz") as mock_fitz,
        ):
            mock_fitz.open.side_effect = [mock_doc, mock_output_doc]
            create_searchable_pdf(input_file, output, progress_callback=progress_messages.append)

        assert any("ページが存在しない" in msg for msg in progress_messages)

    def test_cancel_event_raises(self, tmp_path: Path) -> None:
        """キャンセルでOCRCancelledError。"""
        from image_pdf_ocr._pdf import create_searchable_pdf

        input_file = tmp_path / "input.pdf"
        input_file.write_bytes(b"%PDF-1.4 dummy")
        output = tmp_path / "output.pdf"

        mock_doc = MagicMock()
        mock_doc.page_count = 1
        mock_page = MagicMock()
        mock_doc.__getitem__ = MagicMock(return_value=mock_page)
        mock_doc.__enter__ = MagicMock(return_value=mock_doc)
        mock_doc.__exit__ = MagicMock(return_value=False)

        mock_output_doc = MagicMock()
        mock_output_doc.__enter__ = MagicMock(return_value=mock_output_doc)
        mock_output_doc.__exit__ = MagicMock(return_value=False)

        cancel = Event()
        cancel.set()

        with (
            patch("image_pdf_ocr._pdf.find_and_set_tesseract_path", return_value=True),
            patch(
                "image_pdf_ocr._pdf._find_japanese_font_path", return_value=Path("/fake/font.ttf")
            ),
            patch("image_pdf_ocr._pdf.fitz") as mock_fitz,
            pytest.raises(OCRCancelledError),
        ):
            mock_fitz.open.side_effect = [mock_doc, mock_output_doc]
            create_searchable_pdf(input_file, output, cancel_event=cancel)

    def test_tesseract_not_found(self, tmp_path: Path) -> None:
        """Tesseract未検出でOCRConversionError。"""
        from image_pdf_ocr._pdf import create_searchable_pdf

        with (
            patch("image_pdf_ocr._pdf.find_and_set_tesseract_path", return_value=False),
            pytest.raises(OCRConversionError, match="Tesseract-OCR"),
        ):
            create_searchable_pdf(tmp_path / "in.pdf", tmp_path / "out.pdf")


class TestCreateSearchablePdfFromImages:
    """create_searchable_pdf_from_images のテスト。"""

    def test_no_images_raises(self, tmp_path: Path) -> None:
        """空リストでエラー。"""
        from image_pdf_ocr._pdf import create_searchable_pdf_from_images

        with (
            patch("image_pdf_ocr._pdf.find_and_set_tesseract_path", return_value=True),
            pytest.raises(OCRConversionError, match="1つ以上選択"),
        ):
            create_searchable_pdf_from_images([], tmp_path / "out.pdf")

    def test_invalid_extension_raises(self, tmp_path: Path) -> None:
        """非.pdf拡張子でエラー。"""
        from image_pdf_ocr._pdf import create_searchable_pdf_from_images

        img = tmp_path / "img.png"
        img.write_bytes(b"fake png")

        with (
            patch("image_pdf_ocr._pdf.find_and_set_tesseract_path", return_value=True),
            pytest.raises(OCRConversionError, match=r"\.pdf拡張子"),
        ):
            create_searchable_pdf_from_images([img], tmp_path / "out.txt")

    def test_missing_image_raises(self, tmp_path: Path) -> None:
        """存在しない画像でFileNotFoundError。"""
        from image_pdf_ocr._pdf import create_searchable_pdf_from_images

        missing = tmp_path / "nonexistent.png"

        with (
            patch("image_pdf_ocr._pdf.find_and_set_tesseract_path", return_value=True),
            pytest.raises(FileNotFoundError, match="入力画像が見つかりません"),
        ):
            create_searchable_pdf_from_images([missing], tmp_path / "out.pdf")

    def test_cancel_event_raises(self, tmp_path: Path) -> None:
        """キャンセルでOCRCancelledError。"""
        from image_pdf_ocr._pdf import create_searchable_pdf_from_images

        img = tmp_path / "img.png"
        img.write_bytes(b"fake png")

        cancel = Event()
        cancel.set()

        with (
            patch("image_pdf_ocr._pdf.find_and_set_tesseract_path", return_value=True),
            patch(
                "image_pdf_ocr._pdf._find_japanese_font_path", return_value=Path("/fake/font.ttf")
            ),
            patch("image_pdf_ocr._pdf._determine_canvas_size", return_value=(100, 100)),
            patch("image_pdf_ocr._pdf.fitz") as mock_fitz,
            pytest.raises(OCRCancelledError),
        ):
            mock_output_doc = MagicMock()
            mock_output_doc.__enter__ = MagicMock(return_value=mock_output_doc)
            mock_output_doc.__exit__ = MagicMock(return_value=False)
            mock_fitz.open.return_value = mock_output_doc
            mock_fitz.Rect.return_value = MagicMock()

            create_searchable_pdf_from_images([img], tmp_path / "out.pdf", cancel_event=cancel)

    def test_tesseract_not_found(self, tmp_path: Path) -> None:
        """Tesseract未検出でOCRConversionError。"""
        from image_pdf_ocr._pdf import create_searchable_pdf_from_images

        with (
            patch("image_pdf_ocr._pdf.find_and_set_tesseract_path", return_value=False),
            pytest.raises(OCRConversionError, match="Tesseract-OCR"),
        ):
            create_searchable_pdf_from_images([tmp_path / "img.png"], tmp_path / "out.pdf")


class TestExtractTextFromImagePdf:
    """extract_text_from_image_pdf のテスト。"""

    def test_input_not_found(self, tmp_path: Path) -> None:
        """入力ファイルが存在しない場合 FileNotFoundError。"""
        from image_pdf_ocr._pdf import extract_text_from_image_pdf

        missing = tmp_path / "missing.pdf"

        with (
            patch("image_pdf_ocr._pdf.find_and_set_tesseract_path", return_value=True),
            pytest.raises(FileNotFoundError, match="入力ファイルが見つかりません"),
        ):
            extract_text_from_image_pdf(missing)

    def test_empty_pdf_returns_newline(self, tmp_path: Path) -> None:
        """0ページPDFで'\\n'返却。"""
        from image_pdf_ocr._pdf import extract_text_from_image_pdf

        input_file = tmp_path / "empty.pdf"
        input_file.write_bytes(b"%PDF-1.4 dummy")

        mock_doc = MagicMock()
        mock_doc.page_count = 0
        mock_doc.__enter__ = MagicMock(return_value=mock_doc)
        mock_doc.__exit__ = MagicMock(return_value=False)

        with (
            patch("image_pdf_ocr._pdf.find_and_set_tesseract_path", return_value=True),
            patch("image_pdf_ocr._pdf.fitz") as mock_fitz,
        ):
            mock_fitz.open.return_value = mock_doc
            result = extract_text_from_image_pdf(input_file)

        assert result == "\n"

    def test_cancel_event_raises(self, tmp_path: Path) -> None:
        """キャンセルでOCRCancelledError。"""
        from image_pdf_ocr._pdf import extract_text_from_image_pdf

        input_file = tmp_path / "input.pdf"
        input_file.write_bytes(b"%PDF-1.4 dummy")

        mock_doc = MagicMock()
        mock_doc.page_count = 1
        mock_page = MagicMock()
        mock_doc.__getitem__ = MagicMock(return_value=mock_page)
        mock_doc.__enter__ = MagicMock(return_value=mock_doc)
        mock_doc.__exit__ = MagicMock(return_value=False)

        cancel = Event()
        cancel.set()

        with (
            patch("image_pdf_ocr._pdf.find_and_set_tesseract_path", return_value=True),
            patch("image_pdf_ocr._pdf.fitz") as mock_fitz,
            pytest.raises(OCRCancelledError),
        ):
            mock_fitz.open.return_value = mock_doc
            extract_text_from_image_pdf(input_file, cancel_event=cancel)

    def test_tesseract_not_found(self, tmp_path: Path) -> None:
        """Tesseract未検出でOCRConversionError。"""
        from image_pdf_ocr._pdf import extract_text_from_image_pdf

        with (
            patch("image_pdf_ocr._pdf.find_and_set_tesseract_path", return_value=False),
            pytest.raises(OCRConversionError, match="Tesseract-OCR"),
        ):
            extract_text_from_image_pdf(tmp_path / "in.pdf")

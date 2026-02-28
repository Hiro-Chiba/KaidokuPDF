"""remove_pdf_password のテスト。"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from image_pdf_ocr.ocr import PDFPasswordRemovalError, remove_pdf_password


class TestRemovePdfPassword:
    """remove_pdf_password の全エラーパスおよび正常系をテストする。"""

    def test_input_file_not_found(self, tmp_path: Path) -> None:
        """入力ファイルが存在しない場合 FileNotFoundError。"""
        missing = tmp_path / "missing.pdf"
        output = tmp_path / "output.pdf"
        with pytest.raises(FileNotFoundError, match="入力PDFが見つかりません"):
            remove_pdf_password(missing, output, "password")

    def test_same_input_output_path(self, tmp_path: Path) -> None:
        """入力と出力が同一パスの場合 ValueError。"""
        pdf_file = tmp_path / "same.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 dummy")
        with pytest.raises(ValueError, match="入力と同じ場所には保存できません"):
            remove_pdf_password(pdf_file, pdf_file, "password")

    @patch("image_pdf_ocr._pdf.fitz")
    def test_not_encrypted_pdf(self, mock_fitz: MagicMock, tmp_path: Path) -> None:
        """パスワード未保護PDFの場合 PDFPasswordRemovalError。"""
        pdf_file = tmp_path / "input.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 dummy")
        output = tmp_path / "output.pdf"

        mock_doc = MagicMock()
        mock_doc.is_encrypted = False
        mock_doc.__enter__ = MagicMock(return_value=mock_doc)
        mock_doc.__exit__ = MagicMock(return_value=False)
        mock_fitz.open.return_value = mock_doc

        with pytest.raises(PDFPasswordRemovalError, match="パスワードで保護されていません"):
            remove_pdf_password(pdf_file, output, "password")

    @patch("image_pdf_ocr._pdf.fitz")
    def test_empty_password(self, mock_fitz: MagicMock, tmp_path: Path) -> None:
        """空パスワードの場合 PDFPasswordRemovalError。"""
        pdf_file = tmp_path / "input.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 dummy")
        output = tmp_path / "output.pdf"

        mock_doc = MagicMock()
        mock_doc.is_encrypted = True
        mock_doc.__enter__ = MagicMock(return_value=mock_doc)
        mock_doc.__exit__ = MagicMock(return_value=False)
        mock_fitz.open.return_value = mock_doc

        with pytest.raises(PDFPasswordRemovalError, match="パスワードを入力してください"):
            remove_pdf_password(pdf_file, output, "")

    @patch("image_pdf_ocr._pdf.fitz")
    def test_wrong_password(self, mock_fitz: MagicMock, tmp_path: Path) -> None:
        """誤パスワードの場合 PDFPasswordRemovalError。"""
        pdf_file = tmp_path / "input.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 dummy")
        output = tmp_path / "output.pdf"

        mock_doc = MagicMock()
        mock_doc.is_encrypted = True
        mock_doc.authenticate.return_value = False
        mock_doc.__enter__ = MagicMock(return_value=mock_doc)
        mock_doc.__exit__ = MagicMock(return_value=False)
        mock_fitz.open.return_value = mock_doc

        with pytest.raises(PDFPasswordRemovalError, match="パスワードが正しくありません"):
            remove_pdf_password(pdf_file, output, "wrong")

    @patch("image_pdf_ocr._pdf.fitz")
    def test_save_runtime_error(self, mock_fitz: MagicMock, tmp_path: Path) -> None:
        """保存時 RuntimeError → PDFPasswordRemovalError。"""
        pdf_file = tmp_path / "input.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 dummy")
        output = tmp_path / "output.pdf"

        mock_doc = MagicMock()
        mock_doc.is_encrypted = True
        mock_doc.authenticate.return_value = True
        mock_doc.save.side_effect = RuntimeError("disk full")
        mock_doc.__enter__ = MagicMock(return_value=mock_doc)
        mock_doc.__exit__ = MagicMock(return_value=False)
        mock_fitz.open.return_value = mock_doc

        with pytest.raises(PDFPasswordRemovalError, match="PDFの保存に失敗しました"):
            remove_pdf_password(pdf_file, output, "correct")

    @patch("image_pdf_ocr._pdf.fitz")
    def test_successful_password_removal(self, mock_fitz: MagicMock, tmp_path: Path) -> None:
        """正常系: save() が encryption=PDF_ENCRYPT_NONE で呼ばれる。"""
        pdf_file = tmp_path / "input.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 dummy")
        output = tmp_path / "out" / "output.pdf"

        mock_doc = MagicMock()
        mock_doc.is_encrypted = True
        mock_doc.authenticate.return_value = True
        mock_doc.__enter__ = MagicMock(return_value=mock_doc)
        mock_doc.__exit__ = MagicMock(return_value=False)
        mock_fitz.open.return_value = mock_doc
        mock_fitz.PDF_ENCRYPT_NONE = 0

        remove_pdf_password(pdf_file, output, "correct")

        mock_doc.save.assert_called_once_with(str(output), encryption=0)
        assert output.parent.exists()

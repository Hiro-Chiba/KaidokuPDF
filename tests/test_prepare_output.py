"""_prepare_output_path / extract_text_to_file のテスト。"""

from __future__ import annotations

from pathlib import Path
from threading import Event
from unittest.mock import MagicMock, patch

import pytest

from image_pdf_ocr.ocr import (
    OCRCancelledError,
    OCRConversionError,
    _prepare_output_path,
    extract_text_to_file,
)


class TestPrepareOutputPath:
    """_prepare_output_path のテスト。"""

    def test_creates_parent_directory(self, tmp_path: Path) -> None:
        """親ディレクトリが自動作成される。"""
        output = tmp_path / "sub" / "deep" / "output.pdf"
        _prepare_output_path(output)
        assert output.parent.exists()

    def test_existing_directory_as_output_raises_error(self, tmp_path: Path) -> None:
        """既存ディレクトリを出力先に指定 → OCRConversionError。"""
        dir_path = tmp_path / "existing_dir"
        dir_path.mkdir()
        with pytest.raises(OCRConversionError, match="ディレクトリを指しています"):
            _prepare_output_path(dir_path)

    def test_normal_path_no_error(self, tmp_path: Path) -> None:
        """正常パス → エラーなし。"""
        output = tmp_path / "output.pdf"
        _prepare_output_path(output)

    def test_existing_parent_no_error(self, tmp_path: Path) -> None:
        """親ディレクトリが既に存在する場合もエラーなし。"""
        output = tmp_path / "output.txt"
        _prepare_output_path(output)


class TestExtractTextToFile:
    """extract_text_to_file のテスト。"""

    @patch("image_pdf_ocr._pdf.extract_text_from_image_pdf")
    @patch("image_pdf_ocr._pdf._prepare_output_path")
    def test_normal_writes_text(
        self,
        mock_prepare: MagicMock,
        mock_extract: MagicMock,
        tmp_path: Path,
    ) -> None:
        """正常系: ファイルにテキストが書き込まれる。"""
        mock_extract.return_value = "抽出されたテキスト\n"
        output = tmp_path / "result.txt"

        extract_text_to_file("dummy_input.pdf", output)

        assert output.read_text(encoding="utf-8") == "抽出されたテキスト\n"
        mock_extract.assert_called_once()

    @patch("image_pdf_ocr._pdf.extract_text_from_image_pdf")
    def test_cancel_raises_error(self, mock_extract: MagicMock, tmp_path: Path) -> None:
        """キャンセル → OCRCancelledError。"""
        mock_extract.return_value = "テスト\n"
        cancel = Event()
        cancel.set()
        output = tmp_path / "result.txt"

        with pytest.raises(OCRCancelledError, match="キャンセル"):
            extract_text_to_file("dummy.pdf", output, cancel_event=cancel)

    @patch("image_pdf_ocr._pdf.extract_text_from_image_pdf")
    @patch("image_pdf_ocr._pdf._prepare_output_path")
    def test_permission_error_raises_ocr_error(
        self,
        mock_prepare: MagicMock,
        mock_extract: MagicMock,
        tmp_path: Path,
    ) -> None:
        """書き込み権限エラー → OCRConversionError。"""
        mock_extract.return_value = "テスト\n"
        output = tmp_path / "readonly.txt"

        with (
            patch.object(Path, "write_text", side_effect=PermissionError("denied")),
            pytest.raises(OCRConversionError, match="書き込めませんでした"),
        ):
            extract_text_to_file("dummy.pdf", output)

    @patch("image_pdf_ocr._pdf.extract_text_from_image_pdf")
    @patch("image_pdf_ocr._pdf._prepare_output_path")
    def test_os_error_raises_ocr_error(
        self,
        mock_prepare: MagicMock,
        mock_extract: MagicMock,
        tmp_path: Path,
    ) -> None:
        """OSError → OCRConversionError。"""
        mock_extract.return_value = "テスト\n"
        output = tmp_path / "bad.txt"

        with (
            patch.object(Path, "write_text", side_effect=OSError("disk error")),
            pytest.raises(OCRConversionError, match="保存できませんでした"),
        ):
            extract_text_to_file("dummy.pdf", output)

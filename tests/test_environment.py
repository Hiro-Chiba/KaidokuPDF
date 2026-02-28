"""_environment モジュールのユニットテスト。"""

from __future__ import annotations

import os
import sys
from unittest.mock import patch

import pytest

from image_pdf_ocr._environment import (
    _candidate_font_directories,
    _try_assign_candidates,
    _validate_tesseract_setting,
    find_and_set_tesseract_path,
)


class TestValidateTesseractSetting:
    @patch("image_pdf_ocr._environment.pytesseract.get_tesseract_version")
    def test_returns_true_when_valid(self, mock_version):
        mock_version.return_value = "5.3.0"
        assert _validate_tesseract_setting() is True

    @patch("image_pdf_ocr._environment.pytesseract.get_tesseract_version")
    def test_returns_false_when_not_found(self, mock_version):
        import pytesseract

        mock_version.side_effect = pytesseract.TesseractNotFoundError()
        assert _validate_tesseract_setting() is False


class TestTryAssignCandidates:
    @patch("image_pdf_ocr._environment._validate_tesseract_setting")
    def test_first_valid_candidate_used(self, mock_validate, tmp_path):
        mock_validate.return_value = True
        p1 = tmp_path / "tesseract1"
        p1.touch()
        p2 = tmp_path / "tesseract2"
        p2.touch()

        assert _try_assign_candidates([p1, p2]) is True
        # validate は p1 で成功するので1回だけ呼ばれる
        mock_validate.assert_called_once()

    @patch("image_pdf_ocr._environment._validate_tesseract_setting", return_value=False)
    def test_no_valid_candidate_returns_false(self, mock_validate, tmp_path):
        p1 = tmp_path / "tesseract"
        p1.touch()

        assert _try_assign_candidates([p1]) is False

    def test_skips_nonexistent_paths(self, tmp_path):
        p1 = tmp_path / "nonexistent"

        assert _try_assign_candidates([p1]) is False


class TestFindAndSetTesseractPath:
    @patch("image_pdf_ocr._environment._validate_tesseract_setting", return_value=True)
    @patch("image_pdf_ocr._environment.pytesseract.pytesseract")
    def test_env_tesseract_cmd_used(self, mock_pytesseract, mock_validate):
        """TESSERACT_CMD 環境変数が優先的に使用される。"""
        mock_pytesseract.tesseract_cmd = "tesseract"
        with (
            patch.dict(os.environ, {"TESSERACT_CMD": "/custom/tesseract"}),
            patch("image_pdf_ocr._environment.Path.exists", return_value=True),
        ):
            result = find_and_set_tesseract_path()
        assert result is True

    @patch("image_pdf_ocr._environment._try_assign_candidates", return_value=False)
    @patch("image_pdf_ocr._environment._validate_tesseract_setting")
    @patch("image_pdf_ocr._environment.which", return_value="/usr/bin/tesseract")
    @patch("image_pdf_ocr._environment.pytesseract.pytesseract")
    def test_which_fallback(self, mock_pytesseract, mock_which, mock_validate, mock_try):
        """環境変数なし→whichで検出。"""
        mock_pytesseract.tesseract_cmd = ""
        # 1回目: 設定済みチェック→False, 2回目: which後→True, 残り→True
        mock_validate.side_effect = [False, True]

        with (
            patch.dict(os.environ, {}, clear=False),
            patch("image_pdf_ocr._environment.Path.exists", return_value=True),
        ):
            for env_name in ("TESSERACT_CMD", "TESSERACT_PATH", "PIL_TESSERACT_CMD"):
                os.environ.pop(env_name, None)
            result = find_and_set_tesseract_path()
        assert result is True

    @patch("image_pdf_ocr._environment._validate_tesseract_setting", return_value=False)
    @patch("image_pdf_ocr._environment._try_assign_candidates", return_value=True)
    @patch("image_pdf_ocr._environment.which", return_value=None)
    @patch("image_pdf_ocr._environment.pytesseract.pytesseract")
    def test_bundle_candidates_searched(
        self, mock_pytesseract, mock_which, mock_try, mock_validate
    ):
        """バンドルパスが探索される。"""
        mock_pytesseract.tesseract_cmd = ""

        with (
            patch.dict(os.environ, {}, clear=False),
            patch("image_pdf_ocr._environment.Path.exists", return_value=False),
        ):
            for env_name in ("TESSERACT_CMD", "TESSERACT_PATH", "PIL_TESSERACT_CMD"):
                os.environ.pop(env_name, None)
            result = find_and_set_tesseract_path()
        assert result is True
        mock_try.assert_called_once()

    @patch("image_pdf_ocr._environment._validate_tesseract_setting", return_value=False)
    @patch("image_pdf_ocr._environment._try_assign_candidates", return_value=False)
    @patch("image_pdf_ocr._environment.which", return_value=None)
    @patch("image_pdf_ocr._environment.pytesseract.pytesseract")
    def test_returns_false_when_all_fail(
        self, mock_pytesseract, mock_which, mock_try, mock_validate
    ):
        """全検出失敗時にFalseを返す。"""
        mock_pytesseract.tesseract_cmd = ""

        with (
            patch.dict(os.environ, {}, clear=False),
            patch("image_pdf_ocr._environment.Path.exists", return_value=False),
        ):
            for env_name in ("TESSERACT_CMD", "TESSERACT_PATH", "PIL_TESSERACT_CMD"):
                os.environ.pop(env_name, None)
            result = find_and_set_tesseract_path()
        assert result is False

    @patch("image_pdf_ocr._environment._validate_tesseract_setting", return_value=True)
    @patch("image_pdf_ocr._environment.pytesseract.pytesseract")
    def test_already_configured_and_valid(self, mock_pytesseract, mock_validate):
        """設定済みcmdが有効ならそのまま返す。"""
        mock_pytesseract.tesseract_cmd = "/usr/bin/tesseract"
        with patch.dict(os.environ, {}, clear=False):
            for env_name in ("TESSERACT_CMD", "TESSERACT_PATH", "PIL_TESSERACT_CMD"):
                os.environ.pop(env_name, None)
            result = find_and_set_tesseract_path()
        assert result is True


class TestCandidateFontDirectoriesExtended:
    def test_env_font_dir_included(self, tmp_path):
        """OCR_JPN_FONT_DIR 環境変数で指定したディレクトリが含まれる。"""
        font_dir = tmp_path / "fonts"
        font_dir.mkdir()

        with patch.dict(os.environ, {"OCR_JPN_FONT_DIR": str(font_dir)}):
            dirs = _candidate_font_directories()
        resolved = [d.resolve() for d in dirs]
        assert font_dir.resolve() in resolved

    @pytest.mark.skipif(sys.platform != "win32", reason="WindowsPath requires Windows")
    def test_windows_fonts_included(self):
        """os.name=='nt' 時にWindowsフォントパスが含まれる。"""
        dirs = _candidate_font_directories()
        dir_strs = [str(d) for d in dirs]
        assert any("Fonts" in s for s in dir_strs)

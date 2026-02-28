"""OCRパイプライン関連のテスト。"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from PIL import Image

from image_pdf_ocr.ocr import (
    OCRConversionError,
    _find_japanese_font_path,
    _perform_adaptive_ocr,
    _preprocess_for_ocr,
    _run_ocr_with_best_config,
)


def _make_conf_frame(conf_value: float) -> pd.DataFrame:
    """テスト用の OCR結果 DataFrame を生成する。"""
    return pd.DataFrame(
        {
            "level": [5, 5],
            "page_num": [1, 1],
            "block_num": [1, 1],
            "par_num": [1, 1],
            "line_num": [1, 1],
            "word_num": [1, 2],
            "left": [10, 50],
            "top": [10, 10],
            "width": [30, 30],
            "height": [20, 20],
            "conf": [conf_value, conf_value],
            "text": ["テスト", "文字"],
        }
    )


class TestRunOcrWithBestConfig:
    """_run_ocr_with_best_config のテスト。"""

    @patch("image_pdf_ocr.ocr._image_to_data")
    def test_returns_best_confidence_result(self, mock_itd: MagicMock) -> None:
        """複数PSM試行で最高信頼度の結果を返す。"""
        low_frame = _make_conf_frame(40.0)
        high_frame = _make_conf_frame(80.0)
        mock_itd.side_effect = [low_frame, high_frame]

        image = Image.new("RGB", (100, 100), "white")
        frame, average = _run_ocr_with_best_config(image)

        assert average == pytest.approx(80.0)
        assert len(frame) == 2

    @patch("image_pdf_ocr.ocr._build_tesseract_configs", return_value=("--oem 1 --psm 6",))
    @patch("image_pdf_ocr.ocr._image_to_data")
    def test_single_config(self, mock_itd: MagicMock, _mock_btc: MagicMock) -> None:
        """単一設定の場合でも正常に動作する。"""
        mock_itd.return_value = _make_conf_frame(70.0)
        image = Image.new("RGB", (100, 100), "white")
        _frame, average = _run_ocr_with_best_config(image)
        assert average == pytest.approx(70.0)

    @patch("image_pdf_ocr.ocr._image_to_data")
    def test_early_stop(self, mock_itd: MagicMock) -> None:
        """信頼度が _EARLY_STOP_CONFIDENCE 以上なら早期打ち止め。"""
        high_frame = _make_conf_frame(95.0)
        mock_itd.return_value = high_frame

        with patch(
            "image_pdf_ocr.ocr._build_tesseract_configs",
            return_value=("--psm 6", "--psm 11", "--psm 3", "--psm 4"),
        ):
            image = Image.new("RGB", (100, 100), "white")
            _run_ocr_with_best_config(image)

        assert mock_itd.call_count == 1

    @patch("image_pdf_ocr.ocr._build_tesseract_configs", return_value=())
    def test_no_configs_returns_empty(self, _mock_btc: MagicMock) -> None:
        """設定が空の場合は空DataFrameと0.0を返す。"""
        image = Image.new("RGB", (100, 100), "white")
        frame, average = _run_ocr_with_best_config(image)
        assert frame.empty
        assert average == 0.0


class TestPerformAdaptiveOcr:
    """_perform_adaptive_ocr のテスト。"""

    @patch("image_pdf_ocr.ocr._run_ocr_with_best_config")
    def test_high_confidence_skips_preprocessing(self, mock_run: MagicMock) -> None:
        """信頼度が高い場合は前処理をスキップする。"""
        mock_run.return_value = (_make_conf_frame(80.0), 80.0)

        image = Image.new("RGB", (100, 100), "white")
        result = _perform_adaptive_ocr(image)

        assert result.used_preprocessing is False
        assert result.average_confidence == pytest.approx(80.0)
        mock_run.assert_called_once()

    @patch("image_pdf_ocr.ocr._run_ocr_with_best_config")
    def test_low_confidence_triggers_preprocessing(self, mock_run: MagicMock) -> None:
        """信頼度が低い場合は前処理を実行する。"""
        low_frame = _make_conf_frame(30.0)
        high_frame = _make_conf_frame(70.0)
        mock_run.side_effect = [(low_frame, 30.0), (high_frame, 70.0)]

        image = Image.new("RGB", (100, 100), "white")
        result = _perform_adaptive_ocr(image)

        assert result.used_preprocessing is True
        assert result.average_confidence == pytest.approx(70.0)
        assert mock_run.call_count == 2

    @patch("image_pdf_ocr.ocr._run_ocr_with_best_config")
    def test_preprocessing_not_better_keeps_original(self, mock_run: MagicMock) -> None:
        """前処理しても改善しない場合は元の結果を返す。"""
        frame = _make_conf_frame(40.0)
        mock_run.side_effect = [(frame, 40.0), (frame, 35.0)]

        image = Image.new("RGB", (100, 100), "white")
        result = _perform_adaptive_ocr(image)

        assert result.used_preprocessing is False
        assert result.average_confidence == pytest.approx(40.0)


class TestPreprocessForOcr:
    """_preprocess_for_ocr のテスト。"""

    def test_returns_image_and_scale(self) -> None:
        """返り値が (Image, float) であること。"""
        image = Image.new("RGB", (200, 100), "white")
        result_image, scale = _preprocess_for_ocr(image)
        assert isinstance(result_image, Image.Image)
        assert isinstance(scale, float)

    def test_scale_matches_upscale_factor(self) -> None:
        """scale値が _UPSCALE_FACTOR と一致すること。"""
        from image_pdf_ocr.ocr import _UPSCALE_FACTOR

        image = Image.new("RGB", (200, 100), "white")
        _, scale = _preprocess_for_ocr(image)
        assert scale == pytest.approx(_UPSCALE_FACTOR)

    def test_output_is_grayscale(self) -> None:
        """出力画像が "L" モードであること。"""
        image = Image.new("RGB", (200, 100), "red")
        result_image, _ = _preprocess_for_ocr(image)
        assert result_image.mode == "L"

    def test_output_dimensions_are_scaled(self) -> None:
        """出力画像の寸法がスケーリングされていること。"""
        from image_pdf_ocr.ocr import _UPSCALE_FACTOR

        image = Image.new("RGB", (200, 100), "white")
        result_image, _ = _preprocess_for_ocr(image)
        expected_w = int(200 * _UPSCALE_FACTOR)
        expected_h = int(100 * _UPSCALE_FACTOR)
        assert result_image.size == (expected_w, expected_h)


class TestFindJapaneseFontPath:
    """_find_japanese_font_path のテスト。"""

    def test_env_ocr_jpn_font_found(self, tmp_path: Path) -> None:
        """環境変数 OCR_JPN_FONT 指定時にそのパスを返す。"""
        import image_pdf_ocr.ocr as ocr_module

        font_file = tmp_path / "test_font.ttf"
        font_file.write_bytes(b"fake font data")

        original_cache = ocr_module._FONT_PATH_CACHE
        ocr_module._FONT_PATH_CACHE = None
        try:
            with patch.dict(os.environ, {"OCR_JPN_FONT": str(font_file)}):
                result = _find_japanese_font_path()
                assert result == font_file
        finally:
            ocr_module._FONT_PATH_CACHE = original_cache

    def test_font_not_found_raises_error(self) -> None:
        """フォント未発見 → OCRConversionError。"""
        import image_pdf_ocr.ocr as ocr_module

        original_cache = ocr_module._FONT_PATH_CACHE
        ocr_module._FONT_PATH_CACHE = None
        try:
            with (
                patch.dict(os.environ, {}, clear=True),
                patch.object(Path, "exists", return_value=False),
                patch.object(Path, "is_file", return_value=False),
                patch(
                    "image_pdf_ocr.ocr._candidate_font_directories",
                    return_value=[],
                ),
                patch.dict(os.environ, {"OCR_JPN_FONT": ""}, clear=False),
            ):
                env_backup = os.environ.pop("OCR_JPN_FONT", None)
                try:
                    with pytest.raises(OCRConversionError, match="日本語フォントが見つかりません"):
                        _find_japanese_font_path()
                finally:
                    if env_backup is not None:
                        os.environ["OCR_JPN_FONT"] = env_backup
        finally:
            ocr_module._FONT_PATH_CACHE = original_cache

    def test_cached_font_path_returned(self, tmp_path: Path) -> None:
        """キャッシュされたフォントパスがそのまま返る。"""
        import image_pdf_ocr.ocr as ocr_module

        font_file = tmp_path / "cached_font.ttf"
        font_file.write_bytes(b"fake font data")

        original_cache = ocr_module._FONT_PATH_CACHE
        ocr_module._FONT_PATH_CACHE = font_file
        try:
            result = _find_japanese_font_path()
            assert result == font_file
        finally:
            ocr_module._FONT_PATH_CACHE = original_cache

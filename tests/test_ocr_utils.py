"""image_pdf_ocr.ocr の純粋関数に対するユニットテスト。"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from image_pdf_ocr.ocr import (
    _build_progress_message,
    _build_tesseract_configs,
    _candidate_font_directories,
    _compute_average_confidence,
    _extract_coordinates,
    _filter_frame_by_confidence,
    _format_duration,
    _prepare_frame,
    _sanitize_tesseract_config,
)


# ---------------------------------------------------------------------------
# _format_duration
# ---------------------------------------------------------------------------
class TestFormatDuration:
    def test_zero_seconds(self) -> None:
        assert _format_duration(0) == "00:00"

    def test_65_seconds(self) -> None:
        assert _format_duration(65) == "01:05"

    def test_3661_seconds(self) -> None:
        assert _format_duration(3661) == "01:01:01"

    def test_inf(self) -> None:
        assert _format_duration(float("inf")) == "不明"

    def test_nan(self) -> None:
        assert _format_duration(float("nan")) == "不明"

    def test_negative(self) -> None:
        assert _format_duration(-10) == "00:00"


# ---------------------------------------------------------------------------
# _build_progress_message
# ---------------------------------------------------------------------------
class TestBuildProgressMessage:
    def test_total_zero(self) -> None:
        result = _build_progress_message(0, 0, 0.0)
        assert "不明" in result

    def test_normal_case(self) -> None:
        import time

        start = time.perf_counter()
        result = _build_progress_message(1, 5, start)
        assert "1/5ページ完了" in result
        assert "残り推定時間" in result


# ---------------------------------------------------------------------------
# _compute_average_confidence
# ---------------------------------------------------------------------------
class TestComputeAverageConfidence:
    def test_normal(self) -> None:
        frame = pd.DataFrame({"conf": [80, 90, 70]})
        avg = _compute_average_confidence(frame)
        assert abs(avg - 80.0) < 1e-6

    def test_no_conf_column(self) -> None:
        frame = pd.DataFrame({"text": ["a", "b"]})
        assert _compute_average_confidence(frame) == 0.0

    def test_empty_dataframe(self) -> None:
        frame = pd.DataFrame({"conf": pd.Series([], dtype=float)})
        assert _compute_average_confidence(frame) == 0.0

    def test_all_negative_one(self) -> None:
        frame = pd.DataFrame({"conf": [-1, -1, -1]})
        assert _compute_average_confidence(frame) == 0.0


# ---------------------------------------------------------------------------
# _extract_coordinates
# ---------------------------------------------------------------------------
class TestExtractCoordinates:
    def test_normal(self) -> None:
        row = pd.Series({"left": 10, "top": 20, "height": 30})
        x, y, h = _extract_coordinates(row)
        assert x == 10.0
        assert y == 20.0
        assert h == 30.0

    def test_nan_value(self) -> None:
        row = pd.Series({"left": float("nan"), "top": 20, "height": 30})
        assert _extract_coordinates(row) == (None, None, None)

    def test_none_value(self) -> None:
        row = pd.Series({"left": None, "top": 20, "height": 30})
        assert _extract_coordinates(row) == (None, None, None)

    def test_non_numeric(self) -> None:
        row = pd.Series({"left": "abc", "top": 20, "height": 30})
        assert _extract_coordinates(row) == (None, None, None)


# ---------------------------------------------------------------------------
# _prepare_frame
# ---------------------------------------------------------------------------
class TestPrepareFrame:
    def test_scale_one(self) -> None:
        frame = pd.DataFrame(
            {"left": [100], "top": [200], "width": [50], "height": [60], "conf": [80]}
        )
        result = _prepare_frame(frame, scale=1.0)
        assert result["left"].iloc[0] == 100.0

    def test_scale_two(self) -> None:
        frame = pd.DataFrame(
            {"left": [100], "top": [200], "width": [50], "height": [60], "conf": [80]}
        )
        result = _prepare_frame(frame, scale=2.0)
        assert result["left"].iloc[0] == 50.0
        assert result["top"].iloc[0] == 100.0
        assert result["conf"].iloc[0] == 80.0  # confはスケールしない


# ---------------------------------------------------------------------------
# _filter_frame_by_confidence
# ---------------------------------------------------------------------------
class TestFilterFrameByConfidence:
    def test_threshold_filter(self) -> None:
        frame = pd.DataFrame({"conf": [30, 60, 90], "text": ["a", "b", "c"]})
        result = _filter_frame_by_confidence(frame, 50.0)
        assert len(result) == 2
        assert list(result["text"]) == ["b", "c"]

    def test_empty_result(self) -> None:
        frame = pd.DataFrame({"conf": [10, 20], "text": ["a", "b"]})
        result = _filter_frame_by_confidence(frame, 100.0)
        assert len(result) == 0

    def test_no_conf_column(self) -> None:
        frame = pd.DataFrame({"text": ["a", "b"]})
        result = _filter_frame_by_confidence(frame, 50.0)
        assert len(result) == 0


# ---------------------------------------------------------------------------
# _build_tesseract_configs
# ---------------------------------------------------------------------------
class TestBuildTesseractConfigs:
    def test_default_configs(self) -> None:
        configs = _build_tesseract_configs()
        assert isinstance(configs, tuple)
        assert len(configs) > 0
        for config in configs:
            assert "--psm" in config

    def test_no_duplicates(self) -> None:
        configs = _build_tesseract_configs()
        assert len(configs) == len(set(configs))


# ---------------------------------------------------------------------------
# _candidate_font_directories
# ---------------------------------------------------------------------------
class TestCandidateFontDirectories:
    def test_returns_list_of_paths(self) -> None:
        dirs = _candidate_font_directories()
        assert isinstance(dirs, list)
        assert all(isinstance(d, Path) for d in dirs)

    def test_no_duplicates(self) -> None:
        dirs = _candidate_font_directories()
        assert len(dirs) == len(set(dirs))


# ---------------------------------------------------------------------------
# _sanitize_tesseract_config
# ---------------------------------------------------------------------------
class TestSanitizeTesseractConfig:
    def test_normal_flags_pass_through(self) -> None:
        assert _sanitize_tesseract_config("--oem 1") == "--oem 1"

    def test_multiple_valid_flags(self) -> None:
        assert _sanitize_tesseract_config("--oem 1 --psm 6") == "--oem 1 --psm 6"

    def test_shell_injection_removed(self) -> None:
        # "1;" はセミコロンを含むため値ごと除去される（安全側に倒す）
        result = _sanitize_tesseract_config("--oem 1; rm -rf /")
        assert result == "--oem"
        # セミコロンなしで値が安全な場合は通過する
        result2 = _sanitize_tesseract_config("--oem 1 --psm 6")
        assert result2 == "--oem 1 --psm 6"

    def test_pipe_injection_removed(self) -> None:
        result = _sanitize_tesseract_config("--oem 1 | cat /etc/passwd")
        assert result == "--oem 1"

    def test_ampersand_injection_removed(self) -> None:
        result = _sanitize_tesseract_config("--oem 1 && echo pwned")
        assert result == "--oem 1"

    def test_empty_string(self) -> None:
        assert _sanitize_tesseract_config("") == ""

    def test_unknown_flag_removed(self) -> None:
        result = _sanitize_tesseract_config("--oem 1 --unknown-flag value")
        assert result == "--oem 1"

    def test_tessdata_dir_allowed(self) -> None:
        result = _sanitize_tesseract_config("--tessdata-dir /usr/share/tessdata")
        assert result == "--tessdata-dir /usr/share/tessdata"

    def test_lang_flag_allowed(self) -> None:
        assert _sanitize_tesseract_config("-l jpn") == "-l jpn"

    def test_dpi_flag_allowed(self) -> None:
        assert _sanitize_tesseract_config("--dpi 300") == "--dpi 300"

    def test_backtick_injection_removed(self) -> None:
        result = _sanitize_tesseract_config("--oem `whoami`")
        assert result == "--oem"

    def test_dollar_injection_removed(self) -> None:
        result = _sanitize_tesseract_config("--oem $(cat /etc/passwd)")
        assert result == "--oem"

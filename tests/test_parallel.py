"""_parallel モジュールのユニットテスト（モックベース）。"""

from __future__ import annotations

import os
from threading import Event
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from PIL import Image

from image_pdf_ocr._engine import AdaptiveOCRResult
from image_pdf_ocr._exceptions import OCRCancelledError
from image_pdf_ocr._parallel import (
    _get_max_workers,
    _is_parallel_enabled,
    _ocr_worker,
    _ocr_worker_with_text,
    _run_sequential,
    _worker_initializer,
    run_parallel_ocr,
    run_parallel_ocr_with_text,
)


class TestGetMaxWorkers:
    def test_default_uses_cpu_count(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("KAIDOKU_OCR_WORKERS", None)
            result = _get_max_workers()
            cpu_count = os.cpu_count() or 2
            assert result == max(1, cpu_count // 2)

    def test_env_variable_overrides(self):
        with patch.dict(os.environ, {"KAIDOKU_OCR_WORKERS": "4"}):
            assert _get_max_workers() == 4

    def test_env_variable_minimum_is_1(self):
        with patch.dict(os.environ, {"KAIDOKU_OCR_WORKERS": "0"}):
            assert _get_max_workers() == 1

    def test_invalid_env_variable_falls_back(self):
        with patch.dict(os.environ, {"KAIDOKU_OCR_WORKERS": "abc"}):
            result = _get_max_workers()
            assert result >= 1


class TestIsParallelEnabled:
    def test_enabled_by_default(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("KAIDOKU_PARALLEL", None)
            assert _is_parallel_enabled() is True

    def test_disabled_when_zero(self):
        with patch.dict(os.environ, {"KAIDOKU_PARALLEL": "0"}):
            assert _is_parallel_enabled() is False

    def test_enabled_when_one(self):
        with patch.dict(os.environ, {"KAIDOKU_PARALLEL": "1"}):
            assert _is_parallel_enabled() is True


class TestWorkerInitializer:
    @patch("image_pdf_ocr._parallel.find_and_set_tesseract_path")
    def test_calls_find_and_set(self, mock_find):
        _worker_initializer()
        mock_find.assert_called_once()


class TestOcrWorker:
    @patch("image_pdf_ocr._parallel._filter_frame_by_confidence")
    @patch("image_pdf_ocr._parallel._perform_adaptive_ocr")
    def test_returns_result_and_filtered_rows(self, mock_ocr, mock_filter):
        dummy_frame = pd.DataFrame({"text": ["hello"], "conf": [90.0]})
        mock_ocr.return_value = AdaptiveOCRResult(
            frame=dummy_frame,
            average_confidence=90.0,
            image_for_string=Image.new("RGB", (10, 10)),
            used_preprocessing=False,
        )
        mock_filter.return_value = dummy_frame

        img = Image.new("RGB", (100, 100))
        result, rows = _ocr_worker(img)

        assert isinstance(result, AdaptiveOCRResult)
        assert len(rows) == 1
        assert rows[0]["text"] == "hello"


class TestOcrWorkerWithText:
    @patch("image_pdf_ocr._parallel._perform_adaptive_ocr")
    def test_returns_result_and_text(self, mock_ocr):
        dummy_frame = pd.DataFrame(
            {
                "text": ["hello", "world"],
                "conf": [90.0, 85.0],
                "block_num": [1, 1],
                "par_num": [1, 1],
                "line_num": [1, 1],
            }
        )
        mock_ocr.return_value = AdaptiveOCRResult(
            frame=dummy_frame,
            average_confidence=90.0,
            image_for_string=Image.new("RGB", (10, 10)),
            used_preprocessing=False,
        )

        img = Image.new("RGB", (100, 100))
        result, text = _ocr_worker_with_text(img)

        assert isinstance(result, AdaptiveOCRResult)
        assert "hello" in text
        assert "world" in text


class TestRunParallelOcr:
    def test_empty_images_returns_empty(self):
        assert run_parallel_ocr([]) == []

    @patch("image_pdf_ocr._parallel._ocr_worker")
    @patch("image_pdf_ocr._parallel._is_parallel_enabled", return_value=False)
    def test_sequential_fallback_when_disabled(self, mock_enabled, mock_worker):
        dummy_frame = pd.DataFrame({"text": ["a"], "conf": [80.0]})
        mock_worker.return_value = (
            AdaptiveOCRResult(
                frame=dummy_frame,
                average_confidence=80.0,
                image_for_string=Image.new("RGB", (10, 10)),
                used_preprocessing=False,
            ),
            [{"text": "a"}],
        )

        images = [Image.new("RGB", (50, 50)), Image.new("RGB", (50, 50))]
        results = run_parallel_ocr(images)

        assert len(results) == 2
        mock_worker.assert_called()

    @patch("image_pdf_ocr._parallel._ocr_worker")
    def test_sequential_for_single_image(self, mock_worker):
        dummy_frame = pd.DataFrame({"text": ["a"], "conf": [80.0]})
        mock_worker.return_value = (
            AdaptiveOCRResult(
                frame=dummy_frame,
                average_confidence=80.0,
                image_for_string=Image.new("RGB", (10, 10)),
                used_preprocessing=False,
            ),
            [{"text": "a"}],
        )

        images = [Image.new("RGB", (50, 50))]
        results = run_parallel_ocr(images)

        assert len(results) == 1

    def test_cancel_event_raises(self):
        cancel = Event()
        cancel.set()

        images = [Image.new("RGB", (50, 50))]
        with pytest.raises(OCRCancelledError):
            _run_sequential(images, lambda x: x, cancel, None)

    @patch("image_pdf_ocr._parallel._ocr_worker")
    def test_progress_callback_called(self, mock_worker):
        dummy_frame = pd.DataFrame({"text": ["a"], "conf": [80.0]})
        mock_worker.return_value = (
            AdaptiveOCRResult(
                frame=dummy_frame,
                average_confidence=80.0,
                image_for_string=Image.new("RGB", (10, 10)),
                used_preprocessing=False,
            ),
            [{"text": "a"}],
        )

        progress = MagicMock()
        images = [Image.new("RGB", (50, 50))]
        run_parallel_ocr(images, progress_callback=progress)

        progress.assert_called_once_with(1, 1)

    @patch("image_pdf_ocr._parallel._ocr_worker")
    @patch("image_pdf_ocr._parallel._is_parallel_enabled", return_value=False)
    def test_results_maintain_page_order(self, mock_enabled, mock_worker):
        call_count = 0

        def side_effect(img):
            nonlocal call_count
            call_count += 1
            dummy_frame = pd.DataFrame({"text": [f"page{call_count}"], "conf": [80.0]})
            return (
                AdaptiveOCRResult(
                    frame=dummy_frame,
                    average_confidence=80.0,
                    image_for_string=Image.new("RGB", (10, 10)),
                    used_preprocessing=False,
                ),
                [{"text": f"page{call_count}"}],
            )

        mock_worker.side_effect = side_effect

        images = [Image.new("RGB", (50, 50)) for _ in range(3)]
        results = run_parallel_ocr(images)

        assert len(results) == 3
        assert results[0][1][0]["text"] == "page1"
        assert results[1][1][0]["text"] == "page2"
        assert results[2][1][0]["text"] == "page3"


class TestRunParallelOcrWithText:
    def test_empty_images_returns_empty(self):
        assert run_parallel_ocr_with_text([]) == []

    @patch("image_pdf_ocr._parallel._ocr_worker_with_text")
    @patch("image_pdf_ocr._parallel._is_parallel_enabled", return_value=False)
    def test_sequential_fallback(self, mock_enabled, mock_worker):
        dummy_frame = pd.DataFrame({"text": ["a"], "conf": [80.0]})
        mock_worker.return_value = (
            AdaptiveOCRResult(
                frame=dummy_frame,
                average_confidence=80.0,
                image_for_string=Image.new("RGB", (10, 10)),
                used_preprocessing=False,
            ),
            "extracted text",
        )

        images = [Image.new("RGB", (50, 50)), Image.new("RGB", (50, 50))]
        results = run_parallel_ocr_with_text(images)

        assert len(results) == 2
        assert results[0][1] == "extracted text"


class TestPoolFallback:
    @patch("image_pdf_ocr._parallel._run_sequential")
    @patch(
        "image_pdf_ocr._parallel._run_with_pool",
        side_effect=OSError("pool failed"),
    )
    @patch("image_pdf_ocr._parallel._is_parallel_enabled", return_value=True)
    def test_falls_back_to_sequential_on_pool_error(self, mock_enabled, mock_pool, mock_seq):
        dummy_frame = pd.DataFrame({"text": ["a"], "conf": [80.0]})
        mock_seq.return_value = [
            (
                AdaptiveOCRResult(
                    frame=dummy_frame,
                    average_confidence=80.0,
                    image_for_string=Image.new("RGB", (10, 10)),
                    used_preprocessing=False,
                ),
                [{"text": "a"}],
            )
        ] * 2

        images = [Image.new("RGB", (50, 50)), Image.new("RGB", (50, 50))]
        results = run_parallel_ocr(images)

        assert len(results) == 2
        mock_seq.assert_called_once()
